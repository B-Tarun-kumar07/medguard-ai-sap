"""Small transparent inventory and coverage calculations used by the planning agent."""

from datetime import datetime, timedelta, timezone
from math import isfinite


def days_of_stock(usable_stock: float | None, average_daily_demand: float | None) -> float | None:
    if usable_stock is None or average_daily_demand is None:
        return None
    if not isfinite(float(usable_stock)) or not isfinite(float(average_daily_demand)):
        return None
    if average_daily_demand <= 0 or usable_stock < 0:
        return None
    return float(usable_stock) / float(average_daily_demand)


def uncovered_quantity(current_stock: float, daily_demand: float | None, arrival_days: float | None) -> float | None:
    if daily_demand is None or arrival_days is None or daily_demand < 0 or arrival_days < 0:
        return None
    if not isfinite(float(daily_demand)) or not isfinite(float(arrival_days)):
        return None
    return max(0.0, float(daily_demand) * float(arrival_days) - max(0.0, float(current_stock)))


def shortage_timestamp(days_remaining: float | None) -> str | None:
    if days_remaining is None or days_remaining < 0 or not isfinite(float(days_remaining)):
        return None
    value = datetime.now(timezone.utc) + timedelta(days=float(days_remaining))
    return value.isoformat(timespec="minutes").replace("+00:00", "Z")


def round_units(value: float) -> int:
    return max(0, int(round(float(value))))
