"""Load scraped JSON into Postgres and embed it into Qdrant for RAG.

    python -m app.scripts.ingest_scraped              # all files in app/data/scraped/
    python -m app.scripts.ingest_scraped --states ca

For each app/data/scraped/{state}.json produced by scrape_sources.py:
  1. Postgres: replace that state's rows in `scraped_chunks` (idempotent —
     re-running after a fresh scrape swaps the data cleanly).
  2. Qdrant:   embed every chunk's text (OpenAI text-embedding-3-small) and
     upsert into the `source_chunks` collection. The payload carries the same
     provenance keys as the JSON (state, category, topic, source_url, page…),
     so a vector hit can be turned straight into a citation.

RAG flow this enables: user question -> embed question -> Qdrant nearest
chunks (filtered by state) -> hand chunks to the LLM as context -> answer
with real citations (url + page number).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import date

from qdrant_client import models as qmodels
from sqlalchemy import delete, func, select

from app.config import settings
from app.core.database import AsyncSessionLocal, create_all
from app.core.logging import configure_logging, get_logger
from app.db.models import ScrapedChunk, State
from app.vector.client import get_qdrant
from app.vector.embeddings import EMBEDDING_DIM, embed_texts

log = get_logger(__name__)

SCRAPED_DIR = settings.data_dir.parent / "scraped"
COLLECTION = "source_chunks"
EMBED_BATCH = 64


async def ensure_collection() -> bool:
    client = get_qdrant()
    if client is None:
        return False
    existing = {c.name for c in (await client.get_collections()).collections}
    if COLLECTION not in existing:
        await client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qmodels.VectorParams(
                size=EMBEDDING_DIM, distance=qmodels.Distance.COSINE
            ),
        )
        log.info("created qdrant collection %s", COLLECTION)
    return True


async def ingest_state_pg(db, payload: dict) -> list[ScrapedChunk]:
    """Replace one state's rows in Postgres; returns the inserted ORM rows."""
    state = payload["state"]
    if await db.get(State, state) is None:
        log.warning("state %s not in states table; run seed_data first", state)
        return []

    await db.execute(delete(ScrapedChunk).where(ScrapedChunk.state_code == state))
    rows: list[ScrapedChunk] = []
    for c in payload["chunks"]:
        rows.append(
            ScrapedChunk(
                id=uuid.uuid4(),
                state_code=c["state"],
                category=c["category"],
                topic=c["topic"],
                source_name=c["source_name"],
                source_url=c["source_url"],
                doc_type=c["doc_type"],
                page_number=c["page_number"],
                chunk_index=c["chunk_index"],
                text=c["text"],
                content_hash=c["content_hash"],
                scraped_at=date.fromisoformat(c["scraped_at"]),
            )
        )
    db.add_all(rows)
    await db.commit()
    log.info("[%s] postgres: %d chunks stored", state, len(rows))
    return rows


async def index_chunks_qdrant(rows: list[ScrapedChunk], state: str) -> int:
    client = get_qdrant()
    if client is None:
        log.warning("QDRANT_URL not set — skipping vector indexing")
        return 0
    if not await ensure_collection():
        return 0

    await client.delete(
        collection_name=COLLECTION,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="state_code", match=qmodels.MatchValue(value=state)
                    )
                ]
            )
        ),
    )

    total = 0
    for start in range(0, len(rows), EMBED_BATCH):
        batch = rows[start : start + EMBED_BATCH]
        vectors = await embed_texts([r.text for r in batch])
        points = [
            qmodels.PointStruct(
                id=str(row.id),
                vector=vector,
                payload={
                    "chunk_id": str(row.id),
                    "state_code": row.state_code,
                    "category": row.category,
                    "topic": row.topic,
                    "text": row.text,
                    "source_url": row.source_url,
                    "source_name": row.source_name,
                    "page_number": row.page_number,
                    "doc_type": row.doc_type,
                },
            )
            for row, vector in zip(batch, vectors)
        ]
        await client.upsert(collection_name=COLLECTION, points=points)
        total += len(points)
        log.info("[%s] qdrant: %d/%d embedded", state, total, len(rows))
    return total


async def main(states: list[str] | None) -> None:
    await create_all()
    paths = sorted(SCRAPED_DIR.glob("*.json"))
    if states:
        wanted = {s.strip().lower() for s in states}
        paths = [p for p in paths if p.stem in wanted]
    if not paths:
        log.error(
            "no scraped files found in %s — run scrape_sources first", SCRAPED_DIR
        )
        return

    async with AsyncSessionLocal() as db:
        for path in paths:
            payload = json.loads(path.read_text())
            rows = await ingest_state_pg(db, payload)
            if rows:
                await index_chunks_qdrant(rows, payload["state"])

        count = (await db.execute(select(func.count(ScrapedChunk.id)))).scalar_one()
    log.info("done — scraped_chunks table now holds %d rows", count)


if __name__ == "__main__":
    configure_logging()
    parser = argparse.ArgumentParser(
        description="Ingest scraped JSON into Postgres + Qdrant"
    )
    parser.add_argument("--states", help="comma-separated, e.g. ca,ny")
    args = parser.parse_args()
    asyncio.run(main(args.states.split(",") if args.states else None))
