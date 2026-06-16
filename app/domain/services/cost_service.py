"""Cost-of-moving estimate — fetched live from the LLM.

The previous deterministic implementation (cost_profiles.json + tax-bracket math
+ BEA RPP) is preserved in git history; the curated data file is kept in place
but no longer read. All figures here are AI estimates, not tax advice.
"""

from __future__ import annotations

import time

from app.domain.schemas.cost import (
    CostRequest,
    CostResponse,
    LivingEstimateOut,
    LlmCostResult,
    StateTaxBreakdown,
    TaxSource,
)
from app.llm.factory import run_with_fallback
from app.llm.prompts import COST_DIRECT_SYSTEM, build_cost_direct_prompt

# Generic "where to verify" references (LLM mode has no per-figure citation).
_SOURCES = TaxSource(
    income="https://taxfoundation.org/data/all/state/state-income-tax-rates/",
    property="https://taxfoundation.org/data/all/state/property-taxes-by-state-county/",
    sales="https://taxfoundation.org/data/all/state/state-and-local-sales-tax-rates/",
    col="https://www.bea.gov/data/prices-inflation/regional-price-parities-state-and-metro-area",
)

_CACHE_TTL = 60 * 30
_cache: dict[str, tuple[float, object]] = {}


def _breakdown(c) -> StateTaxBreakdown:
    return StateTaxBreakdown(
        state_code=c.state_code,
        state_name=c.state_name,
        income_tax=c.income_tax,
        property_tax=c.property_tax,
        sales_tax=c.sales_tax,
        total_tax=c.income_tax + c.property_tax + c.sales_tax,
        take_home=c.take_home,
        rpp_index=c.rpp_index,
        sources=_SOURCES,
    )


def _living(c) -> LivingEstimateOut:
    return LivingEstimateOut(
        state_code=c.state_code,
        monthly_rent=c.monthly_rent,
        monthly_groceries=c.monthly_groceries,
        monthly_utilities=c.monthly_utilities,
        monthly_total=c.monthly_rent + c.monthly_groceries + c.monthly_utilities,
    )


class CostService:
    async def compare(self, req: CostRequest) -> CostResponse:
        key = (
            f"cost:{req.from_state}|{req.to_state}|{req.city or ''}|{int(req.salary)}"
            f"|{req.filing}|{req.housing}|{int(req.home_value or 0)}|{int(req.monthly_spending or 0)}"
        )
        cached = _cache.get(key)
        if cached and time.time() - cached[0] < _CACHE_TTL:
            return cached[1]  # type: ignore[return-value]

        prompt = build_cost_direct_prompt(
            req.from_state, req.to_state, req.salary, req.filing,
            req.housing, req.home_value, req.monthly_spending, req.city,
        )
        result, _ = await run_with_fallback(
            None, lambda p: p.structured(COST_DIRECT_SYSTEM, prompt, LlmCostResult)
        )

        from_b = _breakdown(result.from_cost)
        to_b = _breakdown(result.to_cost)
        col_pct = (to_b.rpp_index - from_b.rpp_index) / from_b.rpp_index if from_b.rpp_index else 0.0

        response = CostResponse(
            from_state=req.from_state,
            to_state=req.to_state,
            city=req.city,
            salary=req.salary,
            filing=req.filing,
            housing=req.housing,
            breakdown=[from_b, to_b],
            tax_delta=to_b.total_tax - from_b.total_tax,
            col_pct_diff=round(col_pct, 4),
            salary_equivalence=result.salary_equivalence,
            living_estimates=[_living(result.from_cost), _living(result.to_cost)],
            explanation=result.explanation,
            estimates_available=True,
            disclaimer=(
                "AI-estimated, not tax/financial advice. Figures are approximate — verify with a "
                "professional and the linked references before deciding."
            ),
        )
        _cache[key] = (time.time(), response)
        return response


cost_service = CostService()
