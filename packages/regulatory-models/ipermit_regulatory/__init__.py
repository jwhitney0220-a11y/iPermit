"""iPermit regulatory intelligence models and repository (T00-01 / T02-02 / T02-03)."""

from .confidence import ConfidenceTier, tier_description, validate_tier
from .models import (
    CITATION_TYPES,
    RULE_JURISDICTION_LEVELS,
    RULE_STATUSES,
    RegulatoryCitation,
    RegulatoryRule,
)
from .repository import add_rule, get_rule, to_document, validate_rule

__all__ = [
    "CITATION_TYPES",
    "RULE_JURISDICTION_LEVELS",
    "RULE_STATUSES",
    "ConfidenceTier",
    "RegulatoryCitation",
    "RegulatoryRule",
    "add_rule",
    "get_rule",
    "tier_description",
    "to_document",
    "validate_rule",
    "validate_tier",
]
