"""Cost-of-moving estimator.

Pass 1 — deterministic, sourced math: income/property/sales tax, take-home,
         BEA cost-of-living %, salary equivalence.
Pass 2 — LLM (best-effort): monthly living-cost estimates + explanation,
         grounded by the Pass-1 numbers. Degrades to null if no provider.
"""

from __future__ import annotations

import json

from app.config import settings
from app.core.exceptions import LLMError, UnknownStateError
from app.core.logging import get_logger
from app.domain.schemas.cost import (
    CostRequest,
    CostResponse,
    LivingEstimateOut,
    StateTaxBreakdown,
    TaxSource,
)
from app.llm.factory import run_with_fallback
from app.llm.prompts import build_cost_prompt

log = get_logger(__name__)

TAXABLE_SHARE = 0.5


def _load_profiles() -> dict:
    from app.config import SERVER_ROOT

    path = SERVER_ROOT / "app" / "data" / "cost_profiles.json"
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        log.warning("cost_profiles.json missing — cost endpoint will report unsupported states")
        return {}
    return {k: v for k, v in data.items() if not k.startswith("_")}


_PROFILES = _load_profiles()


def _income_tax(salary: float, filing: str, profile: dict) -> float:
    it = profile["income_tax"]
    kind = it["type"]
    if kind == "none":
        return 0.0
    if kind == "flat":
        return salary * it["rate"]
    brackets = it.get(filing) or it.get("single")
    tax = 0.0
    lower = 0.0
    for upper, rate in brackets:
        upper_eff = upper if upper is not None else float("inf")
        if salary <= lower:
            break
        taxable = min(salary, upper_eff) - lower
        tax += taxable * rate
        lower = upper_eff
    return tax


def _equivalent_salary(
    target_real: float, filing: str, profile: dict, rpp_to: float
) -> float:
    """Solve for gross salary in the destination whose take-home, deflated by the
    destination price index, equals target_real. Bisection handles brackets."""
    lo, hi = 0.0, 5_000_000.0
    for _ in range(60):
        mid = (lo + hi) / 2
        take_home = mid - _income_tax(mid, filing, profile)
        real = take_home / (rpp_to / 100.0)
        if real < target_real:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


class CostService:
    def _breakdown(self, code: str, req: CostRequest) -> StateTaxBreakdown:
        profile = _PROFILES[code]
        income = _income_tax(req.salary, req.filing, profile)
        property_tax = (
            (req.home_value or 0) * profile["property_tax_pct"] / 100
            if req.housing == "own"
            else 0.0
        )
        spending = (
            req.monthly_spending
            if req.monthly_spending is not None
            else req.salary * 0.35 / 12
        )
        sales = spending * 12 * TAXABLE_SHARE * profile["sales_tax_pct"] / 100
        total_tax = income + property_tax + sales
        return StateTaxBreakdown(
            state_code=code,
            state_name=profile["name"],
            income_tax=round(income),
            property_tax=round(property_tax),
            sales_tax=round(sales),
            total_tax=round(total_tax),
            take_home=round(req.salary - income),
            rpp_index=profile["rpp_index"],
            sources=TaxSource(**profile["sources"]),
        )

    async def compare(self, req: CostRequest) -> CostResponse:
        for code in (req.from_state, req.to_state):
            if code not in _PROFILES:
                raise UnknownStateError(f"No cost data for state '{code}'")

        from_b = self._breakdown(req.from_state, req)
        to_b = self._breakdown(req.to_state, req)

        col_pct = (to_b.rpp_index - from_b.rpp_index) / from_b.rpp_index
        real_from = from_b.take_home / (from_b.rpp_index / 100.0)
        equiv = _equivalent_salary(
            real_from, req.filing, _PROFILES[req.to_state], to_b.rpp_index
        )

        living, explanation, available = await self._llm_estimates(req, from_b, to_b)

        return CostResponse(
            from_state=req.from_state,
            to_state=req.to_state,
            city=req.city,
            salary=req.salary,
            filing=req.filing,
            housing=req.housing,
            breakdown=[from_b, to_b],
            tax_delta=to_b.total_tax - from_b.total_tax,
            col_pct_diff=round(col_pct, 4),
            salary_equivalence=round(equiv),
            living_estimates=living,
            explanation=explanation,
            estimates_available=available,
            disclaimer=(
                "Estimates only — not tax, financial, or market advice. Tax and price-index "
                "figures are sourced; living-cost figures are AI estimates. Verify with a "
                "professional before deciding."
            ),
        )

    async def _llm_estimates(self, req: CostRequest, from_b, to_b):
        if not settings.available_providers:
            return None, None, False
        prompt = build_cost_prompt(
            from_b.state_name,
            to_b.state_name,
            req.salary,
            req.housing,
            self._facts(from_b),
            self._facts(to_b),
            req.city,
        )
        try:
            narrative, _ = await run_with_fallback(
                None, lambda p: p.estimate_costs(prompt)
            )
        except LLMError as exc:
            log.warning("cost estimate LLM failed, returning sourced-only: %s", exc)
            return None, None, False

        out = []
        for est, code in (
            (narrative.from_estimate, req.from_state),
            (narrative.to_estimate, req.to_state),
        ):
            total = est.monthly_rent + est.monthly_groceries + est.monthly_utilities
            out.append(
                LivingEstimateOut(
                    state_code=code,
                    monthly_rent=est.monthly_rent,
                    monthly_groceries=est.monthly_groceries,
                    monthly_utilities=est.monthly_utilities,
                    monthly_total=total,
                )
            )
        return out, narrative.explanation, True

    @staticmethod
    def _facts(b: StateTaxBreakdown) -> dict:
        return {
            "state_code": b.state_code,
            "name": b.state_name,
            "rpp_index": b.rpp_index,
            "income_tax": b.income_tax,
            "property_tax": b.property_tax,
            "sales_tax": b.sales_tax,
            "take_home": b.take_home,
        }


cost_service = CostService()
