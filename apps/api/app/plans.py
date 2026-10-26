"""Store plan limits. Matches the pricing on /stores."""

PLANS = {
    "free": {"products": 300, "widget": False, "widget_daily": 0, "insights": False},
    "growth": {"products": 10_000, "widget": True, "widget_daily": 500, "insights": True},
    "brand": {"products": 200_000, "widget": True, "widget_daily": 20_000, "insights": True},
}


def limits(plan: str) -> dict:
    return PLANS.get(plan, PLANS["free"])
