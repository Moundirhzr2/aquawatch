"""Compare native Power BI query results with the source CSV snapshot."""

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(data_dir, results_dir):
    tables = {}
    hashes = {}
    for path in sorted(data_dir.glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            tables[path.stem] = list(csv.DictReader(handle))
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    meters = tables["dim_meters"]
    readings = tables["fct_consumption"]
    invoices = tables["fct_billing"]
    cases = tables["fct_cases"]
    active = [row for row in cases if row["status"] in {"open", "investigating"}]
    imports = tables["fct_imports"]

    def total(rows, column):
        return sum(int(row[column] or 0) for row in rows)

    accepted, rejected = total(imports, "accepted"), total(imports, "rejected")
    expected = {
        "Connected meters": len({row["meter_id"] for row in meters}),
        "Consumption m3": total(readings, "consumption_liters") / 1000,
        "Valid interval share": sum(row["interval_status"] == "valid" for row in readings)
        / len(readings),
        "Reading count": len(readings),
        "Invoice amount to review EUR": total(invoices, "review_amount_cents") / 100,
        "Billed amount EUR": total(invoices, "billed_amount_cents") / 100,
        "Expected amount EUR": total(invoices, "expected_amount_cents") / 100,
        "Flagged invoices": sum(int(row["review_amount_cents"]) > 0 for row in invoices),
        "Active investigations": len(active),
        "Case count": len(cases),
        "Active amount to review EUR": total(active, "amount_cents") / 100,
        "Accepted rows": accepted,
        "Quarantined rows": rejected,
        "Acceptance rate": accepted / (accepted + rejected),
    }
    actual = json.loads((results_dir / "measures.json").read_text(encoding="utf-8-sig"))
    assert set(actual) == {f"[{name}]" for name in expected}, "Unexpected measure result schema"
    for name, value in expected.items():
        assert math.isclose(actual[f"[{name}]"], value, rel_tol=1e-12, abs_tol=1e-9), name
    filters = json.loads((results_dir / "filters.json").read_text(encoding="utf-8-sig"))
    assert filters["tables"] == [{f"[{name}]": len(rows) for name, rows in tables.items()}]
    meter_district = {row["meter_id"]: row["district"] for row in meters}
    by_district = defaultdict(lambda: dict(readings=0, liters=0, cases=0, invoices=0))
    by_date = defaultdict(lambda: dict(readings=0, liters=0, cases=0, invoices=0, network_rows=0))
    for row in readings:
        for bucket in [by_district[meter_district[row["meter_id"]]], by_date[row["reading_date"]]]:
            bucket["readings"] += 1
            bucket["liters"] += int(row["consumption_liters"] or 0)
    for collection, key, date_column in [
        (cases, "cases", "event_date"),
        (invoices, "invoices", "period_end"),
    ]:
        for row in collection:
            by_district[meter_district[row["meter_id"]]][key] += 1
            by_date[row[date_column]][key] += 1
    for row in tables["network_daily"]:
        by_date[row["reading_date"]]["network_rows"] += 1
    for group, column, expected_groups in [
        ("districts", "dim_meters[district]", by_district),
        ("dates", "dim_date[calendar_date]", by_date),
    ]:
        observed = {}
        for row in filters[group]:
            label = row[column][:10] if group == "dates" else row[column]
            assert label not in observed, f"Duplicate filter result: {label}"
            observed[label] = {
                key.strip("[]"): value or 0 for key, value in row.items() if key != column
            }
        assert observed == dict(expected_groups), f"Native {group} filter results differ from CSV"
    summary = {
        "status": "passed",
        "scope": "Native engine Power Query refresh and DAX; visual rendering is not covered",
        "measures_checked": len(expected),
        "table_counts": {name: len(rows) for name, rows in tables.items()},
        "districts_checked": len(by_district),
        "dates_checked": len(by_date),
        "expected_unfiltered_measures": expected,
        "csv_sha256": hashes,
    }
    (results_dir / "parity.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        f"Native Power BI parity passed: {len(expected)} measures, 7 tables, {len(by_district)} districts and {len(by_date)} dates."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "powerbi/data")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "runtime/powerbi-validation")
    arguments = parser.parse_args()
    check(arguments.data_dir, arguments.results_dir)
