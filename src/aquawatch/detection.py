"""Explainable rules, with no access to generator labels or customer names."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date, timedelta
from statistics import median

from .synthetic import invoice_amount

RULE_VERSION = "1.0.0"


def case(meter_id, kind, event_date, severity, title, explanation, evidence, amount_cents=0):
    key = f"{meter_id}|{kind}|{event_date}"
    return dict(
        id=hashlib.sha256(key.encode()).hexdigest()[:16],
        meter_id=meter_id,
        kind=kind,
        event_date=event_date,
        severity=severity,
        title=title,
        explanation=explanation,
        evidence={"rule_version": RULE_VERSION, **evidence},
        amount_cents=amount_cents,
    )


def series(rows):
    """Only consecutive, nondecreasing counters yield valid daily consumption."""
    result, previous = [], None
    for row in sorted(rows, key=lambda r: r["reading_date"]):
        value = None
        if previous:
            gap = (
                date.fromisoformat(row["reading_date"])
                - date.fromisoformat(previous["reading_date"])
            ).days
            delta = row["counter_liters"] - previous["counter_liters"]
            if gap == 1 and delta >= 0:
                value = delta
        result.append({**row, "consumption_liters": value})
        previous = row
    return result


def detect(readings, invoices, tariffs, as_of: str):
    output = []
    grouped = defaultdict(list)
    for row in readings:
        grouped[row["meter_id"]].append(row)
    for mid, raw in grouped.items():
        rows = series(raw)
        for previous, current in zip(rows, rows[1:]):
            pd, cd = (
                date.fromisoformat(previous["reading_date"]),
                date.fromisoformat(current["reading_date"]),
            )
            days = (cd - pd).days
            if days > 1:
                output.append(
                    case(
                        mid,
                        "missing_reading",
                        (pd + timedelta(days=1)).isoformat(),
                        "medium",
                        "Missing meter reading",
                        f"{days - 1} daily reading(s) missing between {pd} and {cd}. The interval is excluded from daily consumption.",
                        dict(previous_date=str(pd), next_date=str(cd), missing_days=days - 1),
                    )
                )
            if current["counter_liters"] < previous["counter_liters"]:
                output.append(
                    case(
                        mid,
                        "meter_reset",
                        str(cd),
                        "high",
                        "Counter moved backwards",
                        "The cumulative counter decreased. Check for a meter replacement, reset or transcription error before using this interval.",
                        dict(
                            previous_liters=previous["counter_liters"],
                            current_liters=current["counter_liters"],
                        ),
                    )
                )
        if rows:
            last = date.fromisoformat(rows[-1]["reading_date"])
            missing = (date.fromisoformat(as_of) - last).days
            if missing > 0:
                output.append(
                    case(
                        mid,
                        "missing_reading",
                        (last + timedelta(days=1)).isoformat(),
                        "medium",
                        "Reading not received",
                        f"No reading received for {missing} day(s) through {as_of}.",
                        dict(previous_date=str(last), as_of=as_of, missing_days=missing),
                    )
                )
        episode_end = -1
        for i in range(15, len(rows) - 2):
            if i <= episode_end:
                continue
            baseline_values = [
                r["consumption_liters"]
                for r in rows[i - 14 : i]
                if r["consumption_liters"] is not None
            ]
            if len(baseline_values) < 10:
                continue
            baseline = median(baseline_values)
            threshold = max(baseline * 3, baseline + 250)
            sample = rows[i : i + 3]
            contiguous = (
                date.fromisoformat(sample[-1]["reading_date"])
                - date.fromisoformat(sample[0]["reading_date"])
            ).days == 2
            if contiguous and all(
                r["consumption_liters"] is not None and r["consumption_liters"] > threshold
                for r in sample
            ):
                episode_end = i + 2
                while (
                    episode_end + 1 < len(rows)
                    and rows[episode_end + 1]["consumption_liters"] is not None
                    and rows[episode_end + 1]["consumption_liters"] > threshold
                ):
                    episode_end += 1
                output.append(
                    case(
                        mid,
                        "sustained_usage",
                        sample[0]["reading_date"],
                        "high",
                        "Sustained unusual consumption",
                        "Three consecutive daily values exceed both 3x the previous 14-day median and that median plus 250 L. Possible leak or changed activity; operator review required.",
                        dict(
                            baseline_liters=baseline,
                            threshold_liters=threshold,
                            daily_liters=[r["consumption_liters"] for r in sample],
                            detected_on=sample[-1]["reading_date"],
                        ),
                    )
                )
    tariff_map = {t["id"]: t for t in tariffs}
    for invoice in invoices:
        t = tariff_map[invoice["tariff_id"]]
        expected = invoice_amount(
            invoice["billed_volume_liters"], t["rate_cents_per_m3"], t["fixed_fee_cents"]
        )
        discrepancy = invoice["billed_amount_cents"] - expected
        if abs(discrepancy) > 1:
            output.append(
                case(
                    invoice["meter_id"],
                    "billing_mismatch",
                    invoice["period_end"],
                    "high",
                    "Invoice does not match tariff",
                    "The invoice total differs from its stated volume multiplied by the synthetic tariff, plus the fixed fee. This is an amount to review, not proven savings.",
                    dict(
                        invoice_id=invoice["id"],
                        tariff_id=t["id"],
                        billed_volume_liters=invoice["billed_volume_liters"],
                        actual_cents=invoice["billed_amount_cents"],
                        expected_cents=expected,
                        signed_difference_cents=discrepancy,
                    ),
                    abs(discrepancy),
                )
            )
    return output
