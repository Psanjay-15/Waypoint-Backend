from __future__ import annotations

import json
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


class GrokProvider(LLMProvider):
    """xAI Grok — OpenAI-compatible API, JSON-object mode + local validation."""

    name = "grok"
    default_model = "grok-3-mini"

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.grok_api_key, base_url=settings.grok_base_url
        )

    async def _generate(
        self, system: str, user: str, schema: type[SchemaT], max_tokens: int
    ) -> SchemaT:
        schema_hint = (
            f"\n\nRespond with ONLY a JSON object matching this JSON Schema:\n"
            f"{json.dumps(schema.model_json_schema())}"
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self.default_model,
                messages=[
                    {"role": "system", "content": system + schema_hint},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise _map_error(exc, self.name) from exc
        text = self._strip_code_fences(resp.choices[0].message.content or "")
        if not text:
            raise LLMError(f"{self.name}: empty response")
        try:
            return schema.model_validate_json(text)
        except Exception as exc:
            raise LLMError(f"{self.name}: invalid structured output ({exc})") from exc

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
                max_tokens=2000,
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
        return await self._generate(PLAN_SYSTEM, user, GeneratedPlan, max_tokens=4096)

    async def estimate_costs(self, user_prompt: str) -> CostNarrative:
        return await self._generate(
            COST_ESTIMATE_SYSTEM, user_prompt, CostNarrative, max_tokens=1024
        )

    async def assess_city(self, user_prompt: str) -> CityFit:
        return await self._generate(
            CITY_FIT_SYSTEM, user_prompt, CityFit, max_tokens=512
        )

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
                max_tokens=600,
            )
        except Exception as exc:
            raise _map_error(exc, self.name) from exc
        return (resp.choices[0].message.content or "").strip()


def _map_error(exc: Exception, provider: str) -> LLMError:
    msg = str(exc).lower()
    if "429" in msg or "rate" in msg or "quota" in msg:
        return RateLimitError(f"{provider}: rate limited ({exc})")
    return LLMError(f"{provider}: {exc}")
