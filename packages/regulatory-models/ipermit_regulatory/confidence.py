"""Confidence Tier Framework for regulatory rules (T02-03).

Defines the three tiers from AGENTS.md § *Permit Confidence Tiers*:

  Tier 1 — Fully supported and verified. Statutory and stable requirements.
  Tier 2 — Supported but partially verified. Potentially variable local
            implementation.
  Tier 3 — Informational/reference only. Requires consultant confirmation.

``ConfidenceTier`` is an ``IntEnum`` so it compares naturally with the integer
stored in ``RegulatoryRule.confidence_tier`` and passes JSON serialisation.
"""

from __future__ import annotations

from enum import IntEnum

_DESCRIPTIONS: dict[int, str] = {
    1: ("Tier 1 — Fully supported and verified. Statutory and stable requirement."),
    2: ("Tier 2 — Partially verified. Implementation may vary by local jurisdiction."),
    3: (
        "Tier 3 — Informational/reference only. "
        "Requires consultant confirmation before relying on this rule."
    ),
}

_VALID_TIERS: frozenset[int] = frozenset({1, 2, 3})


class ConfidenceTier(IntEnum):
    """Enumerated confidence tiers (AGENTS.md *Permit Confidence Tiers*)."""

    VERIFIED = 1
    PARTIAL = 2
    INFORMATIONAL = 3


def validate_tier(tier: int) -> None:
    """Raise ``ValueError`` if *tier* is not one of 1, 2, or 3."""
    if tier not in _VALID_TIERS:
        raise ValueError(f"confidence_tier must be 1, 2, or 3; got {tier!r}")


def tier_description(tier: int) -> str:
    """Return a human-readable description for a confidence tier value.

    Args:
        tier: An integer in ``{1, 2, 3}``.

    Returns:
        A plain-language string suitable for display to analysts.

    Raises:
        ValueError: if *tier* is not a valid tier value.
    """
    validate_tier(tier)
    return _DESCRIPTIONS[tier]
