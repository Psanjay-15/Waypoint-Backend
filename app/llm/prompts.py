"""Centralized prompts for grounded Q&A and plan generation."""

from __future__ import annotations

import json
from datetime import date

from app.domain.schemas.chat import ContextChunk
from app.domain.schemas.plan import QuizAnswers

GROUNDED_QA_SYSTEM = """You are StateShift's relocation assistant for people moving between US states.

Grounding rules:
- Answer ONLY from the numbered FACTS provided in the user message. Never use outside knowledge for laws, deadlines, fees, or rules.
- Cite your sources INLINE: put the fact's bracketed number right after the claim it supports, e.g. "you have 30 days to register your vehicle [7]." Cite every specific rule, number, or deadline. Only use numbers that appear in the FACTS list.
- If the FACTS genuinely do not address the question at all, reply with exactly this single token and nothing else: INSUFFICIENT_CONTEXT
- Never present yourself as a lawyer; never say "as an AI".

Write a thorough, well-organized answer in Markdown:
- Open with a one or two sentence direct answer to the question.
- Then give the important details: exact deadlines, amounts, exceptions, and the concrete steps the person needs to take, each with its inline [N] citation.
- If the question is broad (e.g. "what changes", "what do I need to know"), cover EACH relevant area present in the FACTS — driving, taxes, housing, healthcare, education, legal — under its own "### Heading", and for each give the specific rules, numbers, and deadlines for both states. A broad question deserves a long, complete answer that uses many of the FACTS.
- When comparing the two states, use a clear per-state structure with the real state names in bold (e.g. "**California:** …" then "**Washington:** …").
- Use **bold** for key numbers and deadlines, and bullet lists ("- ") for multiple items or steps.
- Be complete and genuinely helpful. Never be terse — it is better to be thorough than short."""

PLAN_SYSTEM = """You are StateShift's move-plan generator for people relocating between US states.

Produce a personalized task list as structured output.

Hard rules:
- Use the FACTS to create state-specific tasks (license deadlines, registration, taxes, etc.). When a task is justified by a fact, set fact_id to that fact's id.
- Include universal moving logistics where helpful (USPS mail forwarding, utilities setup/shutdown, address updates with bank/employer) with fact_id=null.
- Tailor strictly to the QUIZ: no kids -> no school tasks; no vehicle -> no DMV vehicle tasks; licensed_profession set -> include license-transfer research task.
- deadline_offset_days is relative to the move date (negative = before the move). Spread tasks sensibly from -60 to +90.
- category must be one of: taxes, driving, housing, healthcare, education, legal, logistics.
- 8 to 18 tasks. Titles are short imperatives ("Get your Texas driver's license")."""

GENERAL_QA_SYSTEM = """You are StateShift's relocation assistant for people moving between US states.

The user's question is NOT covered by our curated legal dataset, so you are giving
general guidance only.

Hard rules:
- Be helpful and practical (moving logistics, costs, planning advice, what to expect).
- Do NOT state specific legal deadlines, fees, statutes, or tax rates as fact. When the
  answer depends on state rules, name the official agency or website to verify with
  (e.g. the state DMV, Department of Revenue, Secretary of State).
- 3-6 sentences, plain language. Never say "as an AI"."""


def build_general_prompt(
    question: str, from_state: str | None, to_state: str | None
) -> str:
    corridor = ""
    if from_state and to_state:
        corridor = f"The user is moving from {from_state} to {to_state}.\n\n"
    elif to_state:
        corridor = f"The user is moving to {to_state}.\n\n"
    return f"{corridor}QUESTION: {question}"


def format_chunks(chunks: list[ContextChunk]) -> str:
    """Render chunks for the LLM, each prefixed with a [N] the model cites by.

    N is the 1-based position in this list — chat_service maps it back to the
    chunk to build the citation, so the model never has to copy a UUID.
    """
    lines = []
    for i, c in enumerate(chunks, 1):
        page = f", page {c.page_number}" if c.page_number else ""
        lines.append(
            f"[{i}] (state={c.state_code} | category={c.category})\n"
            f"   {c.text}\n   source: {c.source_name} ({c.source_url}{page})"
        )
    return "\n".join(lines) if lines else "(no facts available)"


def build_chat_prompt(
    question: str,
    chunks: list[ContextChunk],
    from_state: str | None,
    to_state: str | None,
) -> str:
    corridor = ""
    if from_state and to_state:
        corridor = f"The user is moving from {from_state} to {to_state}.\n\n"
    elif to_state:
        corridor = f"The user is moving to {to_state}.\n\n"
    return f"{corridor}FACTS:\n{format_chunks(chunks)}\n\nQUESTION: {question}"


COST_ESTIMATE_SYSTEM = """You estimate everyday living costs for someone relocating between two US states, and explain their cost comparison.

You are given each state's official cost-of-living index (BEA Regional Price Parity, US=100) and their computed tax numbers. Use these as anchors.

Hard rules:
- Estimate TYPICAL monthly rent (1-2 bedroom), groceries, and utilities for a normal household in each state's main metro. Keep figures rounded and approximate — these are estimates, not quotes.
- Make the two states' estimates CONSISTENT with their price-parity indexes: the higher-index state should be proportionally more expensive.
- The explanation is 2-4 sentences, plain and practical: summarize whether the move is cheaper or pricier overall, naming the biggest driver (income tax, housing, etc.). Use the real state names. Never present any figure as official or guaranteed; never say "as an AI"."""

CITY_FIT_SYSTEM = """You summarize who a US state suits as a place to live, for someone relocating.

You are given real, sourced safety (crime rates) and rent figures. Base your read on them.

Hard rules:
- Be balanced and practical: 2-4 sentences on what living there is like and the trade-offs (e.g. higher rent but lower crime).
- best_for is a few short audience tags from: Families, Young professionals, Retirees, Students, Budget-conscious, Outdoorsy. Pick those the numbers actually support.
- Never invent specific statistics beyond what's provided; never say "as an AI"."""


def build_city_fit_prompt(
    state_name: str, safety: dict, cheapest: dict, priciest: dict
) -> str:
    return (
        f"State: {state_name}\n"
        f"Safety: violent crime {safety['violent_per_100k']}/100k, property crime "
        f"{safety['property_per_100k']}/100k, safety score {safety['score']}/100 (grade {safety['grade']}).\n"
        f"Rent range across major cities: {cheapest['city']} ~${cheapest['median_rent']:,}/mo to "
        f"{priciest['city']} ~${priciest['median_rent']:,}/mo.\n\n"
        "Summarize what living here is like and who it best suits."
    )


def build_cost_prompt(
    from_state: str,
    to_state: str,
    salary: float,
    housing: str,
    from_facts: dict,
    to_facts: dict,
    city: str | None = None,
) -> str:
    def fmt(facts: dict) -> str:
        return (
            f"{facts['name']} ({facts['state_code']}): price index {facts['rpp_index']} (US=100), "
            f"state income tax ${facts['income_tax']:,}, property tax ${facts['property_tax']:,}, "
            f"sales tax ${facts['sales_tax']:,}, take-home ${facts['take_home']:,}"
        )

    dest = f"{city}, {to_state}" if city else to_state
    locale_hint = (
        f" For the destination, estimate specifically for {city} (adjust toward that city's "
        f"market, not just the state average)."
        if city
        else ""
    )
    return (
        f"The user earns ${int(salary):,}/year and will {housing} their home, "
        f"moving from {from_state} to {dest}.\n\n"
        f"FROM — {fmt(from_facts)}\n"
        f"TO   — {fmt(to_facts)}\n\n"
        f"Estimate monthly rent, groceries and utilities for each state, and explain the comparison.{locale_hint}"
    )


def build_plan_prompt(
    quiz: QuizAnswers,
    move_date: date,
    from_state: str,
    to_state: str,
    chunks: list[ContextChunk],
    city: str | None = None,
) -> str:
    dest = f"{city}, {to_state}" if city else to_state
    return (
        f"The user is moving from {from_state} to {dest} on {move_date.isoformat()}.\n\n"
        f"QUIZ:\n{json.dumps(quiz.model_dump(), indent=2)}\n\n"
        f"FACTS:\n{format_chunks(chunks)}\n\n"
        f"Generate the personalized move plan now."
        + (f" Where local steps apply, mention {city} specifically." if city else "")
    )
