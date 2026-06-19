"""Domain logic over the states dataset.

Deterministic generators (area profile, move plan, cost comparison) ported from
the frontend so the API is the single source of truth. Numbers are derived
deterministically from names — stable across calls, no randomness.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta

TIER_RENT = {"metro": 1.45, "urban": 1.18, "mid": 1.0, "small": 0.86}
TIER_SCORE = {"metro": 86, "urban": 83, "mid": 80, "small": 77}

FACILITY_BANK = {
    "Healthcare": ["Primary care clinic", "Urgent care center", "Regional hospital", "Dental studio"],
    "Schools": ["Top-rated elementary", "Public high school", "STEM magnet", "Childcare center"],
    "Mobility": ["Transit station", "Protected bike lane", "Grocery anchor", "Rideshare hub"],
    "Lifestyle": ["Neighborhood gym", "Coffee district", "Riverside park", "Farmers market"],
}

NO_SALES_TAX = {"OR", "MT", "NH", "DE", "AK"}


def _seeded(seed: str, lo: int, hi: int) -> int:
    """Deterministic int in [lo, hi] from a string seed."""
    h = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
    r = (h % 1000) / 1000
    return round(lo + r * (hi - lo))


def _city_record(state: dict, city: str | None) -> dict:
    cities = state["cities"]
    if city:
        for c in cities:
            if c["city"] == city:
                return c
    return cities[0]


# ── Area profile (powers Compare / Home) ─────────────────────────────────────
def area_profile(state: dict, city: str | None = None, area: str | None = None) -> dict:
    rec = _city_record(state, city)
    city_name = rec["city"]
    area_name = area if area in rec["areas"] else rec["areas"][0]
    idx = state["costIndex"]
    rent_mult = TIER_RENT.get(rec["tier"], 1.0)

    base_rent = round(1500 * idx * rent_mult)
    grocery = round(470 * idx + _seeded(city_name + "g", -20, 30))
    utilities = round(200 * (idx * 0.6 + 0.5) + _seeded(city_name + "u", -15, 25))
    transport = round(290 * rent_mult + _seeded(city_name + "t", -20, 40))
    base_score = TIER_SCORE.get(rec["tier"], 80)

    safety = _seeded(area_name + "safety", 70, 95)
    walk = _seeded(area_name + "walk", 58, 96)
    family = _seeded(area_name + "family", 66, 93)
    rent_delta = _seeded(area_name + "rent", -180, 340)
    rent = max(700, base_rent + rent_delta)
    monthly_total = rent + grocery + utilities + transport

    peers = sorted(
        ({"name": a, "score": _seeded(a + "safety", 70, 95)} for a in rec["areas"]),
        key=lambda p: -p["score"],
    )
    notes = ["Best near-term match", "Stable residential pocket", "Good backup zone"]

    facility_types = list(FACILITY_BANK)
    facilities = []
    for t in facility_types:
        bank = FACILITY_BANK[t]
        facilities.append(
            {
                "type": t,
                "name": bank[_seeded(area_name + t, 0, len(bank) - 1)],
                "eta": f"{_seeded(area_name + t + 'eta', 3, 14)} min",
                "quality": _seeded(area_name + t + "q", 74, 96),
            }
        )

    return {
        "state": state["name"],
        "city": city_name,
        "area": area_name,
        "fitScore": round((base_score + safety + family + walk) / 4),
        "safety": safety,
        "walkability": walk,
        "familyFit": family,
        "monthlyTotal": monthly_total,
        "snapshot": {
            "climate": state["climate"],
            "tax": state["tax"],
            "jobMarket": state["jobs"],
            "medianCommute": _seeded(city_name + "commute", 16, 34),
            "schools": _seeded(area_name + "schools", 62, 97),
            "costIndex": state["costIndex"],
        },
        "costItems": [
            {"label": "Rent", "value": rent},
            {"label": "Groceries", "value": grocery},
            {"label": "Utilities", "value": utilities},
            {"label": "Transport", "value": transport},
        ],
        "safeNeighborhoods": [
            {"name": p["name"], "score": p["score"], "note": notes[min(i, 2)]}
            for i, p in enumerate(peers)
        ],
        "facilities": facilities,
        "comparisons": [
            {"label": "Housing pressure", "from": 74, "to": min(96, max(46, round(rent / 28)))},
            {"label": "Daily convenience", "from": 69, "to": walk},
            {"label": "Safety confidence", "from": 72, "to": safety},
            {"label": "Job market", "from": 70, "to": state["jobs"]},
        ],
    }


# ── Move plan ────────────────────────────────────────────────────────────────
def _add_days(iso: str, days: int) -> str:
    d = datetime.strptime(iso, "%Y-%m-%d").date()
    return (d + timedelta(days=days)).isoformat()


def build_plan(to_name: str, city: str | None, move_date: str, quiz: dict) -> list[dict]:
    place = city or to_name
    tax = quiz.get("_tax", "")

    tasks = [
        (
            -30,
            f"Line up financing & make offers in {place}" if quiz.get("housing") == "own" else f"Secure housing in {place}",
            "Confirm the neighborhood and school zone before you commit.",
            "Housing",
        ),
        (-14, "File USPS change of address", "Forward mail and update banks, employer, and subscriptions.", "Admin"),
        (-7, f"Set up utilities at your {place} home", "Electricity, water, internet — schedule start dates around move-in.", "Home"),
        (-5, f"Plan for {to_name} taxes ({tax})" if tax else f"Plan for {to_name} taxes", "Update employer withholding once you establish residency.", "Finance"),
        (20, f"Transfer your driver's license to {to_name}", "Bring ID, SSN, and two proofs of address. Often due within 30-90 days.", "DMV"),
        (30, f"Re-register to vote in {to_name}", "Voter registration doesn't transfer between states.", "Civic"),
    ]
    if quiz.get("ownsVehicle"):
        tasks.append((10, f"Switch auto insurance to your {to_name} policy", "Do this before registering — coverage minimums differ by state.", "Insurance"))
        tasks.append((30, f"Register your vehicle in {to_name}", "Some counties require emissions or safety inspection first.", "DMV"))
    if quiz.get("hasKids"):
        tasks.append((-10, f"Enroll kids in {place} schools", "Need proof of address, immunization records, and a birth certificate.", "Family"))
    if quiz.get("hasPets"):
        tasks.append((25, f"Update pet licenses & vet records for {to_name}", "Transfer vaccination records and register locally if required.", "Family"))
    if quiz.get("hasJob"):
        tasks.append((-3, f"Confirm payroll & start details for your {to_name} role", "Update direct deposit and state tax withholding with HR.", "Work"))

    built = [
        {"title": t, "detail": d, "category": c, "due_date": _add_days(move_date, off)}
        for off, t, d, c in tasks
    ]
    built.sort(key=lambda x: x["due_date"])
    return [{"id": f"t{i}", "done": False, **t} for i, t in enumerate(built)]


# ── Cost comparison ──────────────────────────────────────────────────────────
def _income_rate(tax_str: str) -> float:
    s = tax_str.lower()
    if "no " in s and "income" in s:
        return 0.0
    m = re.search(r"([\d.]+)\s*%", s)
    if not m:
        return 0.0
    rate = float(m.group(1)) / 100
    if "progressive" in s:
        rate *= 0.55  # crude effective rate vs the quoted top marginal rate
    return rate


def _state_cost_profile(state: dict) -> dict:
    return {
        "code": state["code"],
        "name": state["name"],
        "income_rate": _income_rate(state["tax"]),
        "property_pct": 1.0,
        "sales_pct": 0.0 if state["code"] in NO_SALES_TAX else 6.5,
        "rpp_index": round(state["costIndex"] * 100, 1),
        "tax_note": state["tax"],
    }


def _breakdown(profile: dict, salary: float, filing: str, housing: str, home_value: float, monthly_spending: float | None) -> dict:
    income = salary * profile["income_rate"]
    property_tax = (home_value or 0) * profile["property_pct"] / 100 if housing == "own" else 0.0
    spending = monthly_spending if monthly_spending is not None else salary * 0.35 / 12
    sales = spending * 12 * 0.5 * profile["sales_pct"] / 100
    return {
        "stateCode": profile["code"],
        "stateName": profile["name"],
        "incomeTax": round(income),
        "propertyTax": round(property_tax),
        "salesTax": round(sales),
        "totalTax": round(income + property_tax + sales),
        "takeHome": round(salary - income),
        "rppIndex": profile["rpp_index"],
        "taxNote": profile["tax_note"],
    }


def _living(state: dict) -> dict:
    idx = state["costIndex"]
    rent = round(1500 * idx)
    groceries = round(470 * idx)
    utilities = round(200 * (idx * 0.6 + 0.5))
    return {
        "stateCode": state["code"],
        "monthlyRent": rent,
        "monthlyGroceries": groceries,
        "monthlyUtilities": utilities,
        "monthlyTotal": rent + groceries + utilities,
    }


def cost_compare(from_state: dict, to_state: dict, req: dict) -> dict:
    fp = _state_cost_profile(from_state)
    tp = _state_cost_profile(to_state)
    salary = req["salary"]
    filing = req.get("filing", "single")
    housing = req.get("housing", "rent")
    home_value = req.get("homeValue") or 0
    spending = req.get("monthlySpending")

    fb = _breakdown(fp, salary, filing, housing, home_value, spending)
    tb = _breakdown(tp, salary, filing, housing, home_value, spending)

    col_pct = (tb["rppIndex"] - fb["rppIndex"]) / fb["rppIndex"]
    real_from = fb["takeHome"] / (fb["rppIndex"] / 100)
    equiv = real_from * (tb["rppIndex"] / 100) / (1 - tp["income_rate"])

    return {
        "fromState": from_state["code"],
        "toState": to_state["code"],
        "city": req.get("city"),
        "salary": salary,
        "filing": filing,
        "housing": housing,
        "breakdown": [fb, tb],
        "livingEstimates": [_living(from_state), _living(to_state)],
        "taxDelta": tb["totalTax"] - fb["totalTax"],
        "colPctDiff": round(col_pct, 4),
        "salaryEquivalence": round(equiv),
        "disclaimer": (
            "Estimates only — not tax, financial, or market advice. Tax rates are "
            "approximations; verify with a professional before deciding."
        ),
    }


# ── Chat grounding helpers ───────────────────────────────────────────────────
def chat_context(to_state: dict, from_name: str, city: str | None) -> str:
    s = to_state
    where = f"{city}, {s['name']}" if city else s["name"]
    return (
        f"Move: {from_name} -> {s['name']} (destination: {where}).\n"
        f"Climate: {s['climate']}.\n"
        f"State income tax: {s['tax']}.\n"
        f"Job market score: {s['jobs']}/100.\n"
        f"Cost of living index: {s['costIndex']}x the national average."
    )


_SOURCE_RULES = [
    (re.compile(r"licen|dmv|driver|vehicle|car|registration|plate"), [
        ("{to} DMV — New Resident Guide", "https://www.dmv.org/"),
    ]),
    (re.compile(r"tax|income|salary|paycheck"), [
        ("{to} Department of Revenue", "https://www.irs.gov/"),
        ("Tax Foundation — State tax maps", "https://taxfoundation.org/"),
    ]),
    (re.compile(r"school|kid|child|enroll"), [
        ("{to} Dept. of Education", "https://www.ed.gov/"),
    ]),
    (re.compile(r"vote|voter|elect"), [
        ("Vote.gov — Register in your new state", "https://vote.gov/"),
    ]),
    (re.compile(r"cost|rent|afford|housing"), [
        ("BLS — Consumer Expenditure data", "https://www.bls.gov/"),
    ]),
]


def chat_sources(question: str, to_name: str) -> list[dict]:
    q = question.lower()
    for pattern, srcs in _SOURCE_RULES:
        if pattern.search(q):
            return [{"title": t.format(to=to_name), "url": u} for t, u in srcs]
    return [{"title": "USA.gov — Moving to a new state", "url": "https://www.usa.gov/"}]


def suggestions(to_name: str) -> list[str]:
    return [
        f"Do I need a new license in {to_name}?",
        f"How does {to_name} income tax work?",
        f"Steps to register my car in {to_name}?",
        "How do I enroll my kids in school?",
    ]
