"""Export actual dbt-built marts for a portable, versioned Power BI project."""

import csv
import os
from pathlib import Path

MARTS = [
    "dim_meters",
    "dim_date",
    "fct_consumption",
    "fct_billing",
    "fct_cases",
    "fct_imports",
    "network_daily",
]


def export_marts(target="local"):
    destination = Path("powerbi/data")
    destination.mkdir(parents=True, exist_ok=True)
    if target == "local":
        import duckdb

        connection = duckdb.connect("runtime/analytics.duckdb", read_only=True)
    else:
        import psycopg

        connection = psycopg.connect(
            host=os.getenv("PGHOST", "127.0.0.1"),
            port=int(os.getenv("PGPORT", "5432")),
            user=os.getenv("PGUSER", "aquawatch"),
            password=os.environ["PGPASSWORD"],
            dbname=os.getenv("PGDATABASE", "aquawatch"),
        )
    try:
        for name in MARTS:
            # Identifiers come only from the fixed allowlist above.
            prefix = "analytics." if target == "postgres" else ""
            cursor = connection.execute(f"select * from {prefix}{name}")
            fields = [column[0] for column in cursor.description]
            with (destination / f"{name}.csv").open("w", encoding="utf-8", newline="") as out:
                writer = csv.writer(out)
                writer.writerow(fields)
                writer.writerows(cursor.fetchall())
    finally:
        connection.close()
    print("Exported seven dbt marts to powerbi/data")
