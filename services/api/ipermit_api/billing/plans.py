"""Plan catalog and entitlements (SAAS-03 / S03-02).

Plans are defined in code (open-saas src/payment/plans.ts pattern), not the
database: they are platform-global product configuration. A tenant's
*subscription* (which plan it is on) is persisted; the plan's *entitlements*
(quotas, feature flags) are looked up here. ``None`` quota means unlimited.
"""

from __future__ import annotations

from dataclasses import dataclass

#: A tenant with no subscription row is treated as this plan.
DEFAULT_PLAN = "free"


@dataclass(frozen=True)
class Plan:
    """A purchasable plan and the entitlements it grants."""

    key: str
    name: str
    monthly_evaluations: int | None
    monthly_exports: int | None
    price_id: str | None  # external processor price id (None for free)


PLANS: dict[str, Plan] = {
    "free": Plan(
        "free", "Free", monthly_evaluations=10, monthly_exports=5, price_id=None
    ),
    "pro": Plan(
        "pro", "Pro", monthly_evaluations=500, monthly_exports=500, price_id="price_pro"
    ),
    "enterprise": Plan(
        "enterprise",
        "Enterprise",
        monthly_evaluations=None,
        monthly_exports=None,
        price_id="price_enterprise",
    ),
}


def get_plan(key: str | None) -> Plan:
    """Return the plan for *key*, falling back to the default plan."""
    return PLANS.get(key or DEFAULT_PLAN, PLANS[DEFAULT_PLAN])


def is_valid_plan(key: str) -> bool:
    """True if *key* names a known, purchasable plan."""
    return key in PLANS
