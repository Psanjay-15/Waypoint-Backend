from __future__ import annotations

import asyncio
from datetime import date
from typing import TypeVar

from google import genai
from google.genai import types as genai_types
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


class GeminiProvider(LLMProvider):
    name = "gemini"
    default_model = "gemini-2.5-flash"

    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)

    async def _generate(self, system: str, user: str, schema: type[SchemaT]) -> SchemaT:
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
        )
        try:
            resp = await asyncio.to_thread(
                self._client.models.generate_content,
                model=self.default_model,
                contents=user,
                config=config,
            )
        except Exception as exc:
            raise _map_error(exc, self.name) from exc

        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        text = self._strip_code_fences(resp.text or "")
        if not text:
            raise LLMError(f"{self.name}: empty response")
        return schema.model_validate_json(text)

    async def grounded_answer(
        self,
        question: str,
        chunks: list[ContextChunk],
        from_state: str | None,
        to_state: str | None,
    ) -> str:
        config = genai_types.GenerateContentConfig(
            system_instruction=GROUNDED_QA_SYSTEM
        )
        try:
            resp = await asyncio.to_thread(
                self._client.models.generate_content,
                model=self.default_model,
                contents=build_chat_prompt(question, chunks, from_state, to_state),
                config=config,
            )
        except Exception as exc:
            raise _map_error(exc, self.name) from exc
        return (resp.text or "").strip()

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
        return await self._generate(PLAN_SYSTEM, user, GeneratedPlan)

    async def estimate_costs(self, user_prompt: str) -> CostNarrative:
        return await self._generate(COST_ESTIMATE_SYSTEM, user_prompt, CostNarrative)

    async def assess_city(self, user_prompt: str) -> CityFit:
        return await self._generate(CITY_FIT_SYSTEM, user_prompt, CityFit)

    async def general_answer(
        self, question: str, from_state: str | None, to_state: str | None
    ) -> str:
        config = genai_types.GenerateContentConfig(system_instruction=GENERAL_QA_SYSTEM)
        try:
            resp = await asyncio.to_thread(
                self._client.models.generate_content,
                model=self.default_model,
                contents=build_general_prompt(question, from_state, to_state),
                config=config,
            )
        except Exception as exc:
            raise _map_error(exc, self.name) from exc
        return (resp.text or "").strip()


def _map_error(exc: Exception, provider: str) -> LLMError:
    msg = str(exc).lower()
    if "resource_exhausted" in msg or "429" in msg or "quota" in msg:
        return RateLimitError(f"{provider}: rate limited ({exc})")
    return LLMError(f"{provider}: {exc}")
