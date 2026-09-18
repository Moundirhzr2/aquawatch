import csv
import io

import pytest
from sqlalchemy import func, select

from aquawatch import db
from aquawatch.detection import detect, series
from aquawatch.evaluation import evaluate
from aquawatch.pipeline import ingest, records
from aquawatch.synthetic import AS_OF, csv_bytes, generate, invoice_amount


def count(engine, table):
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar_one()


def test_seed_determinism_and_rounding():
    assert generate()["csv"] == generate()["csv"]
    assert generate(71)["csv"] != generate(42)["csv"]
    assert invoice_amount(1, 500, 0) == 1
    assert invoice_amount(1, 499, 0) == 0
    assert invoice_amount(1000, 325, 850) == 1175


def test_full_fixture_counts_and_replay(seeded):
    engine, fixture = seeded
    first = ingest(engine, fixture["csv"], "baseline.csv", AS_OF.isoformat())
    assert first["accepted"] == 10796
    assert first["rejected"] == 8
    assert first["duplicates"] == 5
    before = (count(engine, db.readings), count(engine, db.cases), count(engine, db.runs))
    second = ingest(engine, fixture["csv"], "renamed.csv", AS_OF.isoformat())
    assert second["replayed"] and second["id"] == first["id"]
    assert before == (count(engine, db.readings), count(engine, db.cases), count(engine, db.runs))


def test_bad_header_leaves_failed_ledger_without_readings(seeded):
    engine, _ = seeded
    with pytest.raises(ValueError, match="header"):
        ingest(engine, b"meter,date,value\nM-0001,2026-08-29,12\n", "broken.csv", AS_OF.isoformat())
    assert count(engine, db.readings) == 0
    with engine.connect() as conn:
        run = records(conn, db.runs)[0]
        assert run["status"] == "failed"
        assert run["accepted"] == 0


def test_structural_csv_failure_rolls_back_valid_prefix(seeded):
    engine, _ = seeded
    content = b'meter_id,reading_date,counter_liters\nM-0001,2026-08-29,123\n"unterminated'
    with pytest.raises(ValueError):
        ingest(engine, content, "truncated.csv", AS_OF.isoformat())
    assert count(engine, db.readings) == 0
    assert count(engine, db.rejections) == 0


@pytest.mark.parametrize("counter", ["NaN", "-1", "1.5", "2000000001", "１２３", ""])
def test_invalid_counters_are_quarantined(seeded, counter):
    engine, _ = seeded
    run = ingest(
        engine,
        csv_bytes([dict(meter_id="M-0001", reading_date="2026-08-29", counter_liters=counter)]),
        "invalid.csv",
        AS_OF.isoformat(),
    )
    assert run["accepted"] == 0 and run["rejected"] == 1


def test_unknown_meter_and_future_date(seeded):
    engine, _ = seeded
    rows = [
        dict(meter_id="M-9999", reading_date="2026-08-29", counter_liters=120),
        dict(meter_id="M-0001", reading_date="2026-08-31", counter_liters=120),
    ]
    run = ingest(engine, csv_bytes(rows), "invalid.csv", AS_OF.isoformat())
    assert run["accepted"] == 0 and run["rejected"] == 2


def test_conflicting_duplicate_never_overwrites(seeded):
    engine, _ = seeded
    original = dict(meter_id="M-0001", reading_date="2026-08-29", counter_liters=5000)
    run = ingest(
        engine,
        csv_bytes([original, {**original, "counter_liters": 8000}]),
        "duplicate.csv",
        AS_OF.isoformat(),
    )
    assert run["accepted"] == 1 and run["duplicates"] == 1
    with engine.connect() as conn:
        assert records(conn, db.readings)[0]["counter_liters"] == 5000
        assert records(conn, db.rejections)[0]["reason"] == "conflicting_reading"


def test_reset_and_gap_do_not_create_fake_daily_volume():
    raw = [
        dict(reading_date="2026-08-01", counter_liters=1000),
        dict(reading_date="2026-08-02", counter_liters=100),
        dict(reading_date="2026-08-04", counter_liters=1000),
        dict(reading_date="2026-08-05", counter_liters=1200),
    ]
    assert [r["consumption_liters"] for r in series(raw)] == [None, None, None, 200]


def test_detection_does_not_see_future_or_labels():
    rows = [
        r
        for r in csv.DictReader(io.StringIO(generate()["csv"].decode()))
        if r["meter_id"] == "M-0001" and r["reading_date"] <= "2026-08-21"
    ]
    rows = [{**r, "counter_liters": int(r["counter_liters"])} for r in rows]
    assert not any(c["kind"] == "sustained_usage" for c in detect(rows, [], [], "2026-08-21"))


@pytest.mark.parametrize("seed", [42, 71, 103])
def test_benchmark_has_known_misses_and_no_false_alerts(engine, seed):
    from aquawatch.pipeline import bootstrap

    fixture = generate(seed)
    bootstrap(engine, fixture)
    ingest(engine, fixture["csv"], "baseline.csv", AS_OF.isoformat())
    with engine.connect() as conn:
        result = evaluate(records(conn, db.cases), fixture["labels"])
    assert result["true_positives"] == 25
    assert result["false_positives"] == 0
    assert result["false_negatives"] == 4
    assert result["by_kind"]["sustained_usage"]["fn"] == 4


def test_daily_increment_does_not_duplicate_existing_events(seeded):
    engine, fixture = seeded
    ingest(engine, fixture["csv"], "baseline.csv", AS_OF.isoformat())
    before = count(engine, db.cases)
    result = ingest(engine, fixture["daily_csv"], "daily.csv", "2026-08-30")
    assert result["accepted"] == 120
    assert count(engine, db.cases) == before
