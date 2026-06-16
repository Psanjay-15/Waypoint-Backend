"""Shared constants and enums."""

from enum import Enum


class Category(str, Enum):
    taxes = "taxes"
    driving = "driving"
    housing = "housing"
    healthcare = "healthcare"
    education = "education"
    legal = "legal"


CATEGORIES: tuple[str, ...] = tuple(c.value for c in Category)

TASK_PENDING = "pending"
TASK_DONE = "done"
TASK_SKIPPED = "skipped"
TASK_STATUSES: tuple[str, ...] = (TASK_PENDING, TASK_DONE, TASK_SKIPPED)

EMERGENCY_KINDS: tuple[str, ...] = (
    "police",
    "medical",
    "fire",
    "disaster",
    "poison",
    "mental_health",
)

DISCLAIMER = (
    "Informational only — not legal advice. Rules change; always verify with the "
    "linked official source."
)
