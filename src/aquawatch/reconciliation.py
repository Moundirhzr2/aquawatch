"""Conservative invoice-to-meter volume comparison for cumulative daily counters."""

from __future__ import annotations

from datetime import date

VOLUME_TOLERANCE_LITERS = 1000


def reconcile_invoice(invoice: dict, readings: list[dict]) -> dict:
    """Compare endpoint counters only when every daily interval can be trusted.

    An internal gap may still contain the total volume, but it can also hide a
    counter replacement. We therefore leave that period unverified rather than
    presenting a potentially misleading billing discrepancy.
    """
    result = {
        "status": "missing_boundary",
        "measured_volume_liters": None,
        "signed_volume_difference_liters": None,
        "missing_days": 0,
        "reset_events": 0,
        "start_counter_liters": None,
        "end_counter_liters": None,
        "tolerance_liters": VOLUME_TOLERANCE_LITERS,
    }
    try:
        start = date.fromisoformat(invoice["period_start"])
        end = date.fromisoformat(invoice["period_end"])
    except (TypeError, ValueError):
        result["status"] = "invalid_period"
        return result
    if end <= start:
        result["status"] = "invalid_period"
        return result
    period = sorted(
        (row for row in readings if start <= date.fromisoformat(row["reading_date"]) <= end),
        key=lambda row: row["reading_date"],
    )
    if not period:
        return result
    if period[0]["reading_date"] == invoice["period_start"]:
        result["start_counter_liters"] = period[0]["counter_liters"]
    if period[-1]["reading_date"] == invoice["period_end"]:
        result["end_counter_liters"] = period[-1]["counter_liters"]
    if result["start_counter_liters"] is None or result["end_counter_liters"] is None:
        return result
    for previous, current in zip(period, period[1:]):
        days = (
            date.fromisoformat(current["reading_date"])
            - date.fromisoformat(previous["reading_date"])
        ).days
        result["missing_days"] += max(0, days - 1)
        result["reset_events"] += current["counter_liters"] < previous["counter_liters"]
    if result["reset_events"]:
        result["status"] = "counter_reset"
    elif result["missing_days"]:
        result["status"] = "incomplete"
    else:
        measured = result["end_counter_liters"] - result["start_counter_liters"]
        result["measured_volume_liters"] = measured
        result["signed_volume_difference_liters"] = invoice["billed_volume_liters"] - measured
        result["status"] = (
            "mismatch"
            if abs(result["signed_volume_difference_liters"]) > VOLUME_TOLERANCE_LITERS
            else "matched"
        )
    return result
