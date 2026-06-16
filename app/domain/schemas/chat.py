from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.domain.schemas.common import Citation


def _normalize_state(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip().upper()
    if len(v) != 2 or not v.isalpha():
        raise ValueError("state must be a 2-letter code, e.g. 'CA'")
    return v


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    from_state: str | None = None
    to_state: str | None = None
    provider: str | None = Field(None, description="openai | anthropic | gemini | grok")

    _norm_from = field_validator("from_state", mode="before")(_normalize_state)
    _norm_to = field_validator("to_state", mode="before")(_normalize_state)

    @field_validator("question")
    @classmethod
    def _strip_question(cls, v: str) -> str:
        return v.strip()


class ContextChunk(BaseModel):
    """One retrieved piece of grounding context — a curated fact or a chunk of
    scraped official text. Carries everything needed to render a citation."""

    fact_id: str
    state_code: str
    category: str
    text: str
    source_url: str
    source_name: str
    title: str | None = None
    page_number: int | None = None
    last_verified: str | None = None


class GroundedAnswer(BaseModel):
    """Structured output target for all LLM providers (chat).

    Citations are the bracketed [N] numbers shown in the FACTS list — small
    integers the model can copy reliably, unlike 36-char UUIDs.
    """

    answer: str = Field(
        ..., description="Plain-English answer based ONLY on the provided facts."
    )
    citations: list[int] = Field(
        default_factory=list,
        description="The [N] numbers of the facts that support the answer. Use only numbers shown in FACTS.",
    )
    confident: bool = Field(
        ...,
        description="False when the provided facts do not cover the question.",
    )


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confident: bool
    grounded: bool = True
    provider_used: str
    cached: bool = False
    disclaimer: str


class ChatSuggestionsResponse(BaseModel):
    suggestions: list[str]
