from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _normalize_state(v: str) -> str:
    v = v.strip().upper()
    if len(v) != 2 or not v.isalpha():
        raise ValueError("state must be a 2-letter code, e.g. 'CA'")
    return v


class CostRequest(BaseModel):
    from_state: str
    to_state: str
    salary: float = Field(..., gt=0, le=100_000_000)
    filing: str = Field("single", description="single | married")
    housing: str = Field("rent", description="rent | own")
    home_value: float | None = Field(None, ge=0, le=500_000_000)
    monthly_spending: float | None = Field(None, ge=0, le=1_000_000)
    city: str | None = Field(
        None, max_length=120, description="Destination city for living-cost estimates"
    )

    _norm_from = field_validator("from_state", mode="before")(_normalize_state)
    _norm_to = field_validator("to_state", mode="before")(_normalize_state)

    @field_validator("filing", mode="before")
    @classmethod
    def _check_filing(cls, v: str) -> str:
        v = (v or "single").strip().lower()
        return v if v in ("single", "married") else "single"

    @field_validator("housing", mode="before")
    @classmethod
    def _check_housing(cls, v: str) -> str:
        v = (v or "rent").strip().lower()
        return v if v in ("rent", "own") else "rent"


class TaxSource(BaseModel):
    income: str
    property: str
    sales: str
    col: str


class StateTaxBreakdown(BaseModel):
    """Deterministic, sourced figures for one state."""

    state_code: str
    state_name: str
    income_tax: int
    property_tax: int
    sales_tax: int
    total_tax: int
    take_home: int
    rpp_index: float
    sources: TaxSource


class StateLivingEstimate(BaseModel):
    state_code: str
    monthly_rent: int = Field(
        ..., description="Estimated typical monthly rent for a 1-2BR."
    )
    monthly_groceries: int = Field(
        ..., description="Estimated monthly groceries for the household."
    )
    monthly_utilities: int = Field(
        ..., description="Estimated monthly utilities (power, water, internet)."
    )


class CostNarrative(BaseModel):
    """What the LLM returns: per-state living-cost estimates + an explanation."""

    from_estimate: StateLivingEstimate
    to_estimate: StateLivingEstimate
    explanation: str = Field(
        ..., description="2-4 sentence plain-English interpretation of the result."
    )


class LivingEstimateOut(BaseModel):
    state_code: str
    monthly_rent: int
    monthly_groceries: int
    monthly_utilities: int
    monthly_total: int


class LlmStateCost(BaseModel):
    state_code: str
    state_name: str
    income_tax: int
    property_tax: int
    sales_tax: int
    take_home: int
    rpp_index: float
    monthly_rent: int
    monthly_groceries: int
    monthly_utilities: int


class LlmCostResult(BaseModel):
    from_cost: LlmStateCost
    to_cost: LlmStateCost
    salary_equivalence: int
    explanation: str


class CostResponse(BaseModel):
    from_state: str
    to_state: str
    city: str | None = None
    salary: float
    filing: str
    housing: str

    breakdown: list[StateTaxBreakdown]
    tax_delta: int
    col_pct_diff: float
    salary_equivalence: int

    living_estimates: list[LivingEstimateOut] | None = None
    explanation: str | None = None
    estimates_available: bool = False

    disclaimer: str
