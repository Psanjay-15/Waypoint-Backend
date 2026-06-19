"""Ingest the states dataset (app/data/states.json) into MongoDB.

Usage:  python -m app.scripts.ingest
Idempotent — upserts each state by code. Also called automatically on startup
when the states collection is empty (AUTO_SEED).
"""

from __future__ import annotations

import asyncio
import json

from pymongo import UpdateOne

from app.config import settings
from app.core.logging import get_logger
from app.db import close, states_col

log = get_logger(__name__)


def _load() -> list[dict]:
    path = settings.data_dir / "states.json"
    return json.loads(path.read_text())


async def ingest() -> int:
    data = _load()
    ops = [
        UpdateOne({"_id": s["code"]}, {"$set": {**s, "_id": s["code"]}}, upsert=True)
        for s in data
    ]
    if not ops:
        return 0
    result = await states_col().bulk_write(ops, ordered=False)
    return result.upserted_count + result.modified_count


async def _main() -> None:
    count = await ingest()
    total = await states_col().estimated_document_count()
    log.info("ingested %d states (collection now holds ~%d)", count, total)
    await close()


if __name__ == "__main__":
    asyncio.run(_main())
