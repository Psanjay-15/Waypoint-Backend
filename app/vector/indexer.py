"""Index law facts into Qdrant and search them — all failures degrade gracefully."""

from __future__ import annotations

from qdrant_client import models as qmodels

from app.core.exceptions import RetrievalError
from app.core.logging import get_logger
from app.db.models import LawFact
from app.domain.schemas.chat import ContextChunk
from app.vector.client import get_qdrant
from app.vector.embeddings import EMBEDDING_DIM, embed_texts

log = get_logger(__name__)

COLLECTION = "law_chunks"
SOURCE_COLLECTION = "source_chunks"


def _fact_text(fact: LawFact) -> str:
    parts = [fact.title, fact.summary]
    if fact.details:
        parts.append(fact.details)
    return " — ".join(parts)


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


async def index_facts(facts: list[LawFact]) -> int:
    """Embed + upsert facts. Returns number indexed; 0 when disabled/unavailable."""
    client = get_qdrant()
    if client is None or not facts:
        return 0
    try:
        existing = {c.name for c in (await client.get_collections()).collections}
        if COLLECTION in existing:
            await client.delete_collection(COLLECTION)
        await ensure_collection()
        vectors = await embed_texts([_fact_text(f) for f in facts])
    except RetrievalError as exc:
        log.warning("skipping qdrant indexing: %s", exc)
        return 0
    points = [
        qmodels.PointStruct(
            id=str(fact.id),
            vector=vector,
            payload={
                "fact_id": str(fact.id),
                "state_code": fact.state_code,
                "category": fact.category,
                "text": _fact_text(fact),
                "source_url": fact.source_url,
                "source_name": fact.source_name,
            },
        )
        for fact, vector in zip(facts, vectors)
    ]
    await client.upsert(collection_name=COLLECTION, points=points)
    log.info("indexed %d facts into qdrant", len(points))
    return len(points)


def _states_filter(state_codes: list[str]) -> qmodels.Filter | None:
    if not state_codes:
        return None
    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="state_code", match=qmodels.MatchAny(any=state_codes)
            )
        ]
    )


async def _query_collection(
    client, collection: str, vector: list[float], state_codes: list[str], top_k: int
) -> list[dict]:
    """Nearest-neighbor payloads from one collection; [] on any failure."""
    try:
        response = await client.query_points(
            collection_name=collection,
            query=vector,
            limit=top_k,
            query_filter=_states_filter(state_codes),
        )
    except Exception as exc:
        log.warning("qdrant query on %s failed: %s", collection, exc)
        return []
    return [hit.payload or {} for hit in response.points]


async def search_hybrid(
    query: str,
    state_codes: list[str],
    top_k_facts: int = 8,
    top_k_sources: int = 6,
) -> tuple[list[ContextChunk], list[ContextChunk]]:
    """Embed the question once, search both collections, return
    (curated-fact hits, scraped-source hits) as ContextChunks."""
    client = get_qdrant()
    if client is None:
        return [], []
    try:
        vector = (await embed_texts([query]))[0]
    except RetrievalError as exc:
        log.warning("embeddings unavailable, structured-only retrieval: %s", exc)
        return [], []

    fact_hits = await _query_collection(
        client, COLLECTION, vector, state_codes, top_k_facts
    )
    source_hits = await _query_collection(
        client, SOURCE_COLLECTION, vector, state_codes, top_k_sources
    )

    facts = [ContextChunk(**p) for p in fact_hits if "fact_id" in p]
    sources = [
        ContextChunk(
            fact_id=p["chunk_id"],
            state_code=p["state_code"],
            category=p.get("category", "legal"),
            text=p["text"],
            source_url=p["source_url"],
            source_name=p["source_name"],
            title=p["source_name"],
            page_number=p.get("page_number"),
        )
        for p in source_hits
        if "chunk_id" in p
    ]
    return facts, sources
