"""Grounded chat: cache → retrieve → LLM (with fallback) → log."""

from __future__ import annotations

import hashlib
import re
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DISCLAIMER
from app.db.models import ChatLog
from app.db.repositories.chat_repo import chat_repo
from app.domain.schemas.chat import ChatRequest, ChatResponse
from app.domain.schemas.common import Citation
from app.domain.services.retrieval_service import retrieval_service
from app.llm.factory import run_with_fallback

_MARKER_RE = re.compile(r"\s*\[\d+(?:\s*,\s*\d+)*\](?:\[\d+\])*")
_MARKER_FIND_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def _strip_markers(text: str) -> str:
    return _MARKER_RE.sub("", text).strip()


def _parse_markers(text: str) -> list[int]:
    """Pull the cited [N] numbers out of the free-form answer, in first-seen
    order. '[7]', '[7, 8]' and '[7][8]' all yield [7, 8]."""
    out: list[int] = []
    for group in _MARKER_FIND_RE.findall(text):
        for part in group.split(","):
            part = part.strip()
            if part.isdigit() and int(part) not in out:
                out.append(int(part))
    return out


def question_hash(question: str, from_state: str | None, to_state: str | None) -> str:
    normalized = " ".join(question.lower().split())
    raw = f"{normalized}|{from_state or ''}|{to_state or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


class ChatService:
    async def ask(
        self, db: AsyncSession, req: ChatRequest, device_id: str
    ) -> ChatResponse:
        qhash = question_hash(req.question, req.from_state, req.to_state)

        cached = await chat_repo.find_cached(db, qhash)
        if cached is not None:
            return ChatResponse(
                answer=cached.answer,
                citations=[Citation(**c) for c in cached.citations],
                confident=cached.confident,
                provider_used=cached.provider,
                cached=True,
                disclaimer=DISCLAIMER,
            )

        chunks = await retrieval_service.retrieve(
            db, req.question, req.from_state, req.to_state
        )

        started = time.monotonic()
        citations: list[Citation] = []
        grounded = True

        if chunks:
            raw, provider_used = await run_with_fallback(
                req.provider,
                lambda p: p.grounded_answer(
                    req.question, chunks, req.from_state, req.to_state
                ),
            )
            if raw.strip().upper().startswith("INSUFFICIENT_CONTEXT"):
                answer_text, provider_used = await run_with_fallback(
                    req.provider,
                    lambda p: p.general_answer(
                        req.question, req.from_state, req.to_state
                    ),
                )
                confident = False
                grounded = False
            else:
                citations = self._citations_for(_parse_markers(raw), chunks)
                answer_text = _strip_markers(raw)
                confident = bool(citations)
        else:
            answer_text, provider_used = await run_with_fallback(
                req.provider,
                lambda p: p.general_answer(req.question, req.from_state, req.to_state),
            )
            confident = False
            grounded = False

        latency_ms = int((time.monotonic() - started) * 1000)

        await chat_repo.create(
            db,
            ChatLog(
                device_id=device_id,
                question=req.question,
                question_hash=qhash,
                from_state=req.from_state,
                to_state=req.to_state,
                answer=answer_text,
                citations=[c.model_dump(mode="json") for c in citations],
                confident=confident and grounded,
                provider=provider_used,
                latency_ms=latency_ms,
            ),
        )

        return ChatResponse(
            answer=answer_text,
            citations=citations,
            confident=confident,
            grounded=grounded,
            provider_used=provider_used,
            cached=False,
            disclaimer=DISCLAIMER,
        )

    def _citations_for(self, cited: list[int], chunks) -> list[Citation]:
        """Resolve cited [N] numbers against the chunks actually provided — the
        model cites by position, so it cannot invent a source that was never in
        its context. Works uniformly for curated facts and scraped chunks (which
        carry PDF page numbers)."""
        from datetime import date as date_type

        citations: list[Citation] = []
        seen: set[tuple[str, int | None]] = set()
        for n in cited:
            idx = n - 1
            if idx < 0 or idx >= len(chunks):
                continue
            chunk = chunks[idx]
            key = (chunk.source_url, chunk.page_number)
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                Citation(
                    fact_id=chunk.fact_id,
                    title=chunk.title or chunk.source_name,
                    source_url=chunk.source_url,
                    source_name=chunk.source_name,
                    last_verified=(
                        date_type.fromisoformat(chunk.last_verified)
                        if chunk.last_verified
                        else None
                    ),
                    page_number=chunk.page_number,
                )
            )
        return citations


chat_service = ChatService()
