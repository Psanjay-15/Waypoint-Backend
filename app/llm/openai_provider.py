from __future__ import annotations

from datetime import date
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings
from app.core.exceptions import LLMError, RateLimitError
from app.domain.schemas.chat import ContextChunk
from app.domain.schemas.cost import CostNarrative
from app.domain.schemas.livability import CityFit
from app.domain.schemas.plan import GeneratedPlan, QuizAnswers
from app.llm.base import LLMProvider
from app.llm.prompts import (
    CITY_FIT_SYSTEM,
    COST_ESTIMATE_SYSTEM,
    GENERAL_QA_SYSTEM,
    GROUNDED_QA_SYSTEM,
    PLAN_SYSTEM,
    build_chat_prompt,
    build_general_prompt,
    build_plan_prompt,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class OpenAIProvider(LLMProvider):
    name = "openai"
    default_model = "gpt-4o-mini"

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def _parse(
        self, system: str, user: str, schema: type[SchemaT], max_tokens: int
    ) -> SchemaT:
        try:
            resp = await self._client.chat.completions.parse(
                model=self.default_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format=schema,
                max_completion_tokens=max_tokens,
            )
        except Exception as exc:
            raise _map_error(exc, self.name) from exc
        parsed = resp.choices[0].message.parsed
        if parsed is None:
            raise LLMError(f"{self.name}: model returned no parsed output")
        return parsed

    async def grounded_answer(
        self,
        question: str,
        chunks: list[ContextChunk],
        from_state: str | None,
        to_state: str | None,
    ) -> str:
        user = build_chat_prompt(question, chunks, from_state, to_state)
        try:
            resp = await self._client.chat.completions.create(
                model=self.default_model,
                messages=[
                    {"role": "system", "content": GROUNDED_QA_SYSTEM},
                    {"role": "user", "content": user},
                ],
                max_completion_tokens=2000,
            )
        except Exception as exc:
            raise _map_error(exc, self.name) from exc
        return (resp.choices[0].message.content or "").strip()

    async def generate_plan(
        self,
        quiz: QuizAnswers,
        move_date: date,
        from_state: str,
        to_state: str,
        chunks: list[ContextChunk],
        city: str | None = None,
    ) -> GeneratedPlan:
        user = build_plan_prompt(quiz, move_date, from_state, to_state, chunks, city)
        return await self._parse(PLAN_SYSTEM, user, GeneratedPlan, max_tokens=4096)

    async def estimate_costs(self, user_prompt: str) -> CostNarrative:
        return await self._parse(
            COST_ESTIMATE_SYSTEM, user_prompt, CostNarrative, max_tokens=1024
        )

    async def assess_city(self, user_prompt: str) -> CityFit:
        return await self._parse(CITY_FIT_SYSTEM, user_prompt, CityFit, max_tokens=512)

    async def structured(self, system, user, schema, max_tokens: int = 2048):
        return await self._parse(system, user, schema, max_tokens=max_tokens)

    async def general_answer(
        self, question: str, from_state: str | None, to_state: str | None
    ) -> str:
        try:
            resp = await self._client.chat.completions.create(
                model=self.default_model,
                messages=[
                    {"role": "system", "content": GENERAL_QA_SYSTEM},
                    {
                        "role": "user",
                        "content": build_general_prompt(question, from_state, to_state),
                    },
                ],
                max_completion_tokens=600,
            )
        except Exception as exc:
            raise _map_error(exc, self.name) from exc
        return (resp.choices[0].message.content or "").strip()


def _map_error(exc: Exception, provider: str) -> LLMError:
    msg = str(exc).lower()
    if "429" in msg or "rate" in msg or "quota" in msg:
        return RateLimitError(f"{provider}: rate limited ({exc})")
    return LLMError(f"{provider}: {exc}")
