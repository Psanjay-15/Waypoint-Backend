"""Load curated state JSON into Postgres, then index facts into Qdrant.

Run manually:  python -m app.scripts.seed_data   (idempotent — re-runs replace
each state's facts/contacts).  Also invoked from the app lifespan when
AUTO_SEED=true and the states table is empty.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.constants import CATEGORIES, EMERGENCY_KINDS
from app.core.database import AsyncSessionLocal, create_all
from app.core.logging import configure_logging, get_logger
from app.db.models import EmergencyContact, LawFact, State
from app.db.repositories.emergency_repo import emergency_repo
from app.db.repositories.law_fact_repo import law_fact_repo
from app.db.repositories.state_repo import state_repo
from app.vector import indexer

log = get_logger(__name__)


class SeedFact(BaseModel):
    category: str
    topic: str
    comparable_key: str
    title: str = Field(..., max_length=160)
    summary: str
    details: str | None = None
    value_structured: dict | None = None
    is_gotcha: bool = False
    source_url: str
    source_name: str
    last_verified: date


class SeedContact(BaseModel):
    agency_name: str
    kind: str
    phone: str
    url: str | None = None
    hours: str = "24/7"
    city: str | None = None


class SeedState(BaseModel):
    code: str = Field(..., min_length=2, max_length=2)
    name: str
    capital: str
    facts: list[SeedFact]
    emergency_contacts: list[SeedContact] = []


async def _seed_state(db: AsyncSession, seed: SeedState) -> None:
    for fact in seed.facts:
        if fact.category not in CATEGORIES:
            raise ValueError(
                f"{seed.code}: invalid category '{fact.category}' in topic '{fact.topic}'"
            )
    for contact in seed.emergency_contacts:
        if contact.kind not in EMERGENCY_KINDS:
            raise ValueError(f"{seed.code}: invalid emergency kind '{contact.kind}'")

    await db.merge(State(code=seed.code, name=seed.name, capital=seed.capital))
    await db.flush()
    await law_fact_repo.delete_for_state(db, seed.code)
    await emergency_repo.delete_for_state(db, seed.code)
    for fact in seed.facts:
        db.add(LawFact(state_code=seed.code, **fact.model_dump()))
    for contact in seed.emergency_contacts:
        db.add(EmergencyContact(state_code=seed.code, **contact.model_dump()))
    await db.commit()
    log.info(
        "seeded %s: %d facts, %d emergency contacts",
        seed.code,
        len(seed.facts),
        len(seed.emergency_contacts),
    )


async def seed() -> None:
    files = sorted(settings.data_dir.glob("*.json"))
    if not files:
        log.warning("no seed files found in %s", settings.data_dir)
        return
    async with AsyncSessionLocal() as db:
        for path in files:
            seed_state = SeedState.model_validate(json.loads(path.read_text()))
            await _seed_state(db, seed_state)
        facts = await law_fact_repo.list_all(db)
    indexed = await indexer.index_facts(facts)
    if indexed:
        log.info("qdrant index ready (%d chunks)", indexed)
    else:
        log.warning("qdrant indexing skipped — chat will use structured-only retrieval")


async def seed_if_empty() -> None:
    async with AsyncSessionLocal() as db:
        count = await state_repo.count(db)
    if count == 0:
        log.info("states table empty — auto-seeding")
        await seed()
    else:
        log.info("seed skipped (%d states present)", count)


async def main() -> None:
    await create_all()
    await seed()


if __name__ == "__main__":
    configure_logging()
    asyncio.run(main())
