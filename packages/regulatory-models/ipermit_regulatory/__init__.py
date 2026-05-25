"""iPermit regulatory intelligence package.

Regulatory rule storage and supporting logic for EPIC-02:
- models / repository / confidence  — schema + persistence (T02-02 / T02-03)
- temporal                          — effective-rule selection by date (T02-04)
- sources                           — source verification tracking (T02-05)
- freshness                         — data-freshness scoring (T02-07)
- ingest                            — dataset ingestion framework (T02-06)
"""

from .confidence import ConfidenceTier, tier_description, validate_tier
from .freshness import (
    FreshnessLabel,
    freshness_label,
    freshness_score,
    needs_review,
)
from .ingest import (
    IngestError,
    load_rules_from_csv,
    load_rules_from_json,
    normalize,
)
from .models import (
    CITATION_TYPES,
    RULE_JURISDICTION_LEVELS,
    RULE_STATUSES,
    RegulatoryCitation,
    RegulatoryRule,
    SourceCheck,
)
from .repository import add_rule, get_rule, to_document, validate_rule
from .sources import (
    all_checks_for_rule,
    check_history,
    is_currently_reachable,
    latest_check,
    record_check,
)
from .temporal import effective_rule, effective_ruleset, is_governing

__all__ = [
    "CITATION_TYPES",
    "RULE_JURISDICTION_LEVELS",
    "RULE_STATUSES",
    "ConfidenceTier",
    "FreshnessLabel",
    "IngestError",
    "RegulatoryCitation",
    "RegulatoryRule",
    "SourceCheck",
    "add_rule",
    "all_checks_for_rule",
    "check_history",
    "effective_rule",
    "effective_ruleset",
    "freshness_label",
    "freshness_score",
    "get_rule",
    "is_currently_reachable",
    "is_governing",
    "latest_check",
    "load_rules_from_csv",
    "load_rules_from_json",
    "needs_review",
    "normalize",
    "record_check",
    "tier_description",
    "to_document",
    "validate_rule",
    "validate_tier",
]
