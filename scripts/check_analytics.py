"""Cross-check the SQL marts against operational Python calculations."""

import argparse
from collections import defaultdict

from sqlalchemy import text

from aquawatch import db
from aquawatch.detection import series
from aquawatch.pipeline import records
from aquawatch.synthetic import invoice_amount


def check(target):
    engine = db.make_engine()
    with engine.connect() as conn:
        readings = records(conn, db.readings)
        invoices = records(conn, db.invoices)
        tariffs = {t["id"]: t for t in records(conn, db.tariffs)}
        if target == "postgres":
            sql_readings = [
                dict(r)
                for r in conn.execute(
                    text("select reading_id, consumption_liters from analytics.fct_consumption")
                ).mappings()
            ]
            sql_invoices = [
                dict(r)
                for r in conn.execute(
                    text("select invoice_id, expected_amount_cents from analytics.fct_billing")
                ).mappings()
            ]
    if target == "local":
        import duckdb

        with duckdb.connect("runtime/analytics.duckdb", read_only=True) as conn:
            sql_readings = [
                dict(zip(["reading_id", "consumption_liters"], r))
                for r in conn.execute(
                    "select reading_id, consumption_liters from fct_consumption"
                ).fetchall()
            ]
            sql_invoices = [
                dict(zip(["invoice_id", "expected_amount_cents"], r))
                for r in conn.execute(
                    "select invoice_id, expected_amount_cents from fct_billing"
                ).fetchall()
            ]
    grouped = defaultdict(list)
    for row in readings:
        grouped[row["meter_id"]].append(row)
    expected = {
        r["id"]: r["consumption_liters"] for values in grouped.values() for r in series(values)
    }
    assert expected == {r["reading_id"]: r["consumption_liters"] for r in sql_readings}, (
        "Consumption differs between operational Python and SQL mart"
    )
    expected_invoices = {
        i["id"]: invoice_amount(
            i["billed_volume_liters"],
            tariffs[i["tariff_id"]]["rate_cents_per_m3"],
            tariffs[i["tariff_id"]]["fixed_fee_cents"],
        )
        for i in invoices
    }
    assert expected_invoices == {
        r["invoice_id"]: r["expected_amount_cents"] for r in sql_invoices
    }, "Tariff rounding differs between Python and SQL"
    print(
        f"Python / {target} SQL parity passed for {len(expected)} observations and {len(expected_invoices)} invoices"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["local", "postgres"], default="local")
    check(parser.parse_args().target)
