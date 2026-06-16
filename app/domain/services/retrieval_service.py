"""Hybrid retrieval: structured Postgres facts + semantic Qdrant reordering."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import LawFact
from app.db.repositories.law_fact_repo import law_fact_repo
from app.domain.schemas.chat import ContextChunk
from app.vector import indexer

log = get_logger(__name__)

MAX_CHUNKS = 40
PREVIEW_CHARS = 200


def _log_context(
    question: str,
    states: list[str],
    source_hits: list[ContextChunk],
    fact_hits: list[ContextChunk],
    ordered: list[ContextChunk],
) -> None:
    """Print the exact RAG context to the server console for debugging.

    Shows what Qdrant returned (scraped `source_chunks` vs curated `law_chunks`)
    and the final ordered context handed to the LLM, numbered to match the [N]
    citation markers in the prompt.
    """
    source_ids = {c.fact_id for c in source_hits}
    lines = [
        "",
        "=" * 78,
        f"RAG RETRIEVAL  |  corridor={'->'.join(states)}  |  q={question!r}",
        f"  qdrant source_chunks (scraped) hits : {len(source_hits)}",
        f"  qdrant law_chunks (curated) hits    : {len(fact_hits)}",
        f"  final context chunks -> LLM         : {len(ordered)}",
        "-" * 78,
    ]
    for i, c in enumerate(ordered, 1):
        origin = "SCRAPED" if c.fact_id in source_ids else "CURATED"
        page = f" p.{c.page_number}" if c.page_number else ""
        preview = " ".join(c.text.split())[:PREVIEW_CHARS]
        lines.append(
            f"[{i}] {origin} | {c.state_code} | {c.category} | {c.source_name}{page}"
        )
        lines.append(f"     {preview}…")
    lines.append("=" * 78)
    log.info("\n".join(lines))


def _to_chunk(fact: LawFact) -> ContextChunk:
    text = f"{fact.title}: {fact.summary}"
    if fact.details:
        text += f" {fact.details}"
    return ContextChunk(
        fact_id=str(fact.id),
        state_code=fact.state_code,
        category=fact.category,
        text=text,
        source_url=fact.source_url,
        source_name=fact.source_name,
        title=fact.title,
        last_verified=fact.last_verified.isoformat() if fact.last_verified else None,
    )


class RetrievalService:
    async def retrieve(
        self,
        db: AsyncSession,
        question: str,
        from_state: str | None,
        to_state: str | None,
        top_k: int = 8,
    ) -> list[ContextChunk]:
        """Proper RAG retrieval, three layers merged into one context:

        1. Semantic hits from `source_chunks` (scraped official text) — the
           question-specific evidence, ranked first.
        2. Curated corridor facts, with the semantically-closest ones (via
           `law_chunks`) promoted to the front.
        3. The remaining corridor facts as grounded backbone (small enough to
           always include — guarantees deadlines/comparisons are never missed).
        """
        states = [s for s in (from_state, to_state) if s]
        if not states:
            return []

        if len(states) == 2:
            facts = await law_fact_repo.list_for_corridor(db, states[0], states[1])
        else:
            facts = await law_fact_repo.list_for_state(db, states[0])
        structured = {c.fact_id: c for c in (_to_chunk(f) for f in facts)}

        fact_hits, source_hits = await indexer.search_hybrid(
            question, states, top_k_facts=top_k, top_k_sources=6
        )

        ordered: list[ContextChunk] = list(source_hits)
        for chunk in fact_hits:
            if chunk.fact_id in structured:
                ordered.append(structured.pop(chunk.fact_id))
        ordered.extend(structured.values())
        ordered = ordered[:MAX_CHUNKS]

        _log_context(question, states, source_hits, fact_hits, ordered)
        return ordered


retrieval_service = RetrievalService()
