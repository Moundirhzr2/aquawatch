"""Deterministic fixtures; labels are kept separately from detector inputs."""

from __future__ import annotations

import csv
import io
import random
from datetime import date, timedelta

START = date(2026, 6, 1)
AS_OF = START + timedelta(days=89)
DEMO_VOLUME_ERRORS = {29: 12_000, 30: -8_000}


def invoice_amount(volume_liters: int, rate_cents: int, fee_cents: int) -> int:
    """Round nonnegative amounts to cents, half up, using integer arithmetic."""
    return (volume_liters * rate_cents + 500) // 1000 + fee_cents


def csv_bytes(rows: list[dict]) -> bytes:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=["meter_id", "reading_date", "counter_liters"])
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def generate(seed: int = 42, count: int = 120) -> dict:
    rng = random.Random(seed)
    customers, meters, readings, invoices, labels, next_day = [], [], [], [], [], []
    for n in range(1, count + 1):
        mid, cid = f"M-{n:04d}", f"C-{n:04d}"
        segment = "Commercial" if n % 5 == 0 else "Residential"
        customers.append(
            dict(
                id=cid,
                name=f"Synthetic site {n:03d}",
                district=["Centre", "Nord", "Sud", "Est"][n % 4],
                segment=segment,
            )
        )
        meters.append(dict(id=mid, customer_id=cid, installed_on="2025-01-01"))
        base = rng.randint(550, 950) if segment == "Commercial" else rng.randint(160, 390)
        counter, volume = rng.randint(200_000, 900_000), 0
        for day in range(90):
            d = (START + timedelta(days=day)).isoformat()
            daily = max(20, round(base * rng.uniform(0.8, 1.2)))
            if 1 <= n <= 6 and day >= 81:
                daily *= 5
            if 25 <= n <= 28 and day >= 81:
                daily = round(daily * 1.5)  # subtle events deliberately below conservative rule
            if 21 <= n <= 24 and day == 81:
                daily *= 5  # benign one-day activity, not a sustained event
            if day:
                volume += daily
                counter += daily
            if 7 <= n <= 10 and day == 85:
                counter = 100
                labels.append(dict(meter_id=mid, kind="meter_reset", event_date=d))
            if 11 <= n <= 14 and day == 86:
                labels.append(dict(meter_id=mid, kind="missing_reading", event_date=d))
                continue
            readings.append(dict(meter_id=mid, reading_date=d, counter_liters=counter))
            if (1 <= n <= 6 or 25 <= n <= 28) and day == 81:
                labels.append(dict(meter_id=mid, kind="sustained_usage", event_date=d))
        # Separate volume errors from tariff arithmetic errors: these invoices
        # have a mathematically correct total for the wrong stated volume.
        billed_volume = volume + DEMO_VOLUME_ERRORS.get(n, 0)
        if n in DEMO_VOLUME_ERRORS:
            labels.append(dict(meter_id=mid, kind="volume_mismatch", event_date=AS_OF.isoformat()))
        amount = invoice_amount(billed_volume, 325, 850)
        if 15 <= n <= 20:
            amount += 2500 + n * 100
            labels.append(dict(meter_id=mid, kind="billing_mismatch", event_date=AS_OF.isoformat()))
        invoices.append(
            dict(
                id=f"INV-{n:04d}",
                meter_id=mid,
                tariff_id="T-2026",
                period_start=START.isoformat(),
                period_end=AS_OF.isoformat(),
                billed_volume_liters=billed_volume,
                billed_amount_cents=amount,
            )
        )
        next_day.append(
            dict(
                meter_id=mid,
                reading_date=(AS_OF + timedelta(days=1)).isoformat(),
                counter_liters=counter + round(base * (5 if n <= 6 else 1)),
            )
        )
    for n in range(31, min(35, count) + 1):
        duplicate = next(
            row.copy()
            for row in readings
            if row["meter_id"] == f"M-{n:04d}" and row["reading_date"] == AS_OF.isoformat()
        )
        readings.append(duplicate)
        labels.append(
            dict(
                meter_id=duplicate["meter_id"],
                kind="duplicate_reading",
                event_date=duplicate["reading_date"],
            )
        )
    readings.extend(
        [
            dict(meter_id="M-9999", reading_date=AS_OF.isoformat(), counter_liters=120),
            dict(meter_id="M-0001", reading_date="not-a-date", counter_liters=120),
            dict(meter_id="M-0002", reading_date=AS_OF.isoformat(), counter_liters=-10),
        ]
    )
    return dict(
        customers=customers,
        meters=meters,
        tariffs=[dict(id="T-2026", rate_cents_per_m3=325, fixed_fee_cents=850)],
        invoices=invoices,
        csv=csv_bytes(readings),
        daily_csv=csv_bytes(next_day),
        labels=labels,
    )
