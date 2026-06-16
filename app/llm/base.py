"""Abstract LLM provider — every model speaks through this interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from app.domain.schemas.chat import ContextChunk
from app.domain.schemas.cost import CostNarrative
from app.domain.schemas.livability import CityFit
from app.domain.schemas.plan import GeneratedPlan, QuizAnswers


class LLMProvider(ABC):
    name: str = ""
    default_model: str = ""

    @abstractmethod
    async def grounded_answer(
        self,
        question: str,
        chunks: list[ContextChunk],
        from_state: str | None,
        to_state: str | None,
    ) -> str:
        """Free-form Markdown answer grounded in the chunks, with inline [N]
        citation markers. Returns the literal token INSUFFICIENT_CONTEXT when the
        chunks don't address the question. (Free-form, not JSON — small models
        write far more detail when not boxed into a structured-output field.)"""
        ...

    @abstractmethod
    async def generate_plan(
        self,
        quiz: QuizAnswers,
        move_date: date,
        from_state: str,
        to_state: str,
        chunks: list[ContextChunk],
        city: str | None = None,
    ) -> GeneratedPlan:
        """Produce a personalized task list grounded in the provided facts."""
        ...

    @abstractmethod
    async def general_answer(
        self,
        question: str,
        from_state: str | None,
        to_state: str | None,
    ) -> str:
        """Plain (ungrounded) answer for questions the curated facts don't cover.

        Must follow GENERAL_QA_SYSTEM: no specific legal deadlines/fees as fact.
        """
        ...

    @abstractmethod
    async def estimate_costs(self, user_prompt: str) -> CostNarrative:
        """Estimate monthly living costs per state + an explanation, grounded by
        the deterministic numbers passed in user_prompt (COST_ESTIMATE_SYSTEM)."""
        ...

    @abstractmethod
    async def assess_city(self, user_prompt: str) -> CityFit:
        """Summarize who a place suits, grounded in the safety + rent numbers in
        user_prompt (CITY_FIT_SYSTEM)."""
        ...

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()
