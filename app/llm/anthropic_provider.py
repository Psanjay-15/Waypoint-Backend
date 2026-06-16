from __future__ import annotations

from datetime import date
from typing import TypeVar

from anthropic import AsyncAnthropic
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


def _tool_for(schema: type[BaseModel], name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": schema.model_json_schema(),
    }


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    default_model = "claude-sonnet-4-6"

    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call_tool(
        self,
        system: str,
        user: str,
        schema: type[SchemaT],
        tool_name: str,
        max_tokens: int,
    ) -> SchemaT:
        tool = _tool_for(
            schema, tool_name, f"Return the {tool_name} as structured data."
        )
        try:
            resp = await self._client.messages.create(
                model=self.default_model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
            )
        except Exception as exc:
            raise _map_error(exc, self.name) from exc
        for block in resp.content:
            if block.type == "tool_use":
                return schema.model_validate(block.input)
        raise LLMError(f"{self.name}: no tool_use block in response")

    async def grounded_answer(
        self,
        question: str,
        chunks: list[ContextChunk],
        from_state: str | None,
        to_state: str | None,
    ) -> str:
        user = build_chat_prompt(question, chunks, from_state, to_state)
        try:
            resp = await self._client.messages.create(
                model=self.default_model,
                max_tokens=2000,
                system=GROUNDED_QA_SYSTEM,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:
            raise _map_error(exc, self.name) from exc
        for block in resp.content:
            if block.type == "text":
                return block.text.strip()
        raise LLMError(f"{self.name}: no text block in response")

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
        return await self._call_tool(
            PLAN_SYSTEM, user, GeneratedPlan, "move_plan", 4096
        )

    async def estimate_costs(self, user_prompt: str) -> CostNarrative:
        return await self._call_tool(
            COST_ESTIMATE_SYSTEM, user_prompt, CostNarrative, "cost_estimate", 1024
        )

    async def assess_city(self, user_prompt: str) -> CityFit:
        return await self._call_tool(
            CITY_FIT_SYSTEM, user_prompt, CityFit, "city_fit", 512
        )

    async def structured(self, system, user, schema, max_tokens: int = 2048):
        return await self._call_tool(system, user, schema, "extract_data", max_tokens)

    async def general_answer(
        self, question: str, from_state: str | None, to_state: str | None
    ) -> str:
        try:
            resp = await self._client.messages.create(
                model=self.default_model,
                max_tokens=600,
                system=GENERAL_QA_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": build_general_prompt(question, from_state, to_state),
                    }
                ],
            )
        except Exception as exc:
            raise _map_error(exc, self.name) from exc
        for block in resp.content:
            if block.type == "text":
                return block.text.strip()
        raise LLMError(f"{self.name}: no text block in response")


def _map_error(exc: Exception, provider: str) -> LLMError:
    msg = str(exc).lower()
    if "429" in msg or "rate" in msg or "overload" in msg:
        return RateLimitError(f"{provider}: rate limited ({exc})")
    return LLMError(f"{provider}: {exc}")
