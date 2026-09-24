"""Read-only evaluation of independently published cumulative water readings.

The source archive is never imported into the operational database. Household
identifiers and raw measurements are omitted from the summary by default.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZipFile

from .detection import detect, series

MAX_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
MAX_OBSERVATIONS = 500_000
EXPECTED_COLUMNS = ["time", "unixtime", "total_m3"]
DATA_DIRECTORY = Path(__file__).resolve().parents[2] / "runtime" / "external"
HOUSEHOLD_ARCHIVES = {
    "hh-04": DATA_DIRECTORY / "hh-04.zip",
    "hh-14": DATA_DIRECTORY / "hh-14.zip",
}


def evaluate_household(household: str) -> dict:
    """Assess data compatibility and rule burden; no ground-truth scores."""
    archive = HOUSEHOLD_ARCHIVES[household]
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with ZipFile(archive) as bundle:
        matches = [
            entry
            for entry in bundle.infolist()
            if entry.filename.endswith("/smartmeter.csv")
            and not entry.filename.startswith("__MACOSX/")
        ]
        if len(matches) != 1:
            raise ValueError("Expected exactly one household smartmeter.csv")
        entry = matches[0]
        if entry.file_size > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("Uncompressed meter file exceeds the safety limit")
        household = entry.filename.split("/", 1)[0]
        if not household.startswith("hh-") or len(household) != 5:
            raise ValueError("Unexpected household archive layout")
        with bundle.open(entry) as binary:
            from io import TextIOWrapper

            reader = csv.DictReader(TextIOWrapper(binary, encoding="utf-8-sig"), strict=True)
            if reader.fieldnames != EXPECTED_COLUMNS:
                raise ValueError("Unexpected smartmeter.csv columns")
            latest: dict[str, tuple[datetime, int]] = {}
            seen_times = set()
            quality = Counter()
            for row in reader:
                quality["source_rows"] += 1
                if quality["source_rows"] > MAX_OBSERVATIONS:
                    raise ValueError("Observation count exceeds the safety limit")
                if set(row) != set(EXPECTED_COLUMNS) or None in row.values():
                    quality["invalid_rows"] += 1
                    continue
                try:
                    observed = datetime.fromisoformat(row["time"])
                    if observed.tzinfo is None:
                        raise ValueError("Timestamp must include a time zone")
                    observed = observed.astimezone(timezone.utc)
                    if int(row["unixtime"]) != int(observed.timestamp()):
                        raise ValueError("Timestamp and Unix time disagree")
                    m3 = Decimal(row["total_m3"])
                    if not m3.is_finite() or m3 < 0:
                        raise ValueError("Invalid cumulative volume")
                    liters = int((m3 * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                except (ValueError, OverflowError, InvalidOperation):
                    quality["invalid_rows"] += 1
                    continue
                if observed in seen_times:
                    quality["duplicate_timestamps"] += 1
                    continue
                seen_times.add(observed)
                quality["valid_rows"] += 1
                day = observed.date().isoformat()
                if day not in latest or observed > latest[day][0]:
                    latest[day] = (observed, liters)
    if not latest:
        raise ValueError("No valid daily observations")
    daily = [
        {"meter_id": household, "reading_date": day, "counter_liters": latest[day][1]}
        for day in sorted(latest)
    ]
    intervals = series(daily)
    flags = detect(daily, [], [], daily[-1]["reading_date"])
    kinds = Counter(flag["kind"] for flag in flags)
    first, last = (
        datetime.fromisoformat(daily[0]["reading_date"]),
        datetime.fromisoformat(daily[-1]["reading_date"]),
    )
    possible = (last - first).days + 1
    return {
        "source": "https://doi.org/10.5281/zenodo.7506076",
        "archive_sha256": digest,
        "household": household,
        "timezone": "UTC",
        "aggregation": "Last valid cumulative observation per UTC day; m3 rounded to integer liters",
        "source_rows": quality["source_rows"],
        "valid_rows": quality["valid_rows"],
        "invalid_rows": quality["invalid_rows"],
        "duplicate_timestamps": quality["duplicate_timestamps"],
        "first_day": daily[0]["reading_date"],
        "last_day": daily[-1]["reading_date"],
        "daily_observations": len(daily),
        "calendar_days": possible,
        "daily_coverage": round(len(daily) / possible, 4),
        "valid_daily_intervals": sum(row["consumption_liters"] is not None for row in intervals),
        "unusable_daily_intervals": sum(row["consumption_liters"] is None for row in intervals),
        "rule_flags_by_kind": dict(sorted(kinds.items())),
        "rule_flags_total": len(flags),
        "evaluation_scope": "Unlabeled external data compatibility and rule burden only",
        "precision": None,
        "recall": None,
        "limitations": [
            "The source has no matching leak, reset or missing-reading ground-truth labels.",
            "A rule flag is a review candidate, not a confirmed incident or false positive.",
            "Daily last-observation aggregation differs from a utility's daily closing read.",
            "No external invoices or tariffs are available for billing evaluation.",
            "One household cannot establish field performance or population generalization.",
        ],
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate external household water readings")
    parser.add_argument("household", choices=sorted(HOUSEHOLD_ARCHIVES))
    args = parser.parse_args()
    result = evaluate_household(args.household)
    report = json.dumps(result, indent=2) + "\n"
    print(report, end="")


if __name__ == "__main__":
    main()
