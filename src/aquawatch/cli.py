"""Reproducible entry points for operators and CI."""

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from . import db
from .pipeline import bootstrap, ingest, records
from .synthetic import AS_OF, generate


def export_raw(engine):
    target = Path("dbt/seeds")
    target.mkdir(parents=True, exist_ok=True)
    with engine.connect() as conn:
        for table in [
            db.customers,
            db.meters,
            db.tariffs,
            db.invoices,
            db.readings,
            db.cases,
            db.runs,
        ]:
            rows = records(conn, table)
            fields = [c.name for c in table.columns if c.name not in {"evidence"}]
            with (target / f"raw_{table.name}.csv").open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="AquaWatch synthetic utility analytics")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["demo", "generate", "export-raw", "benchmark"]:
        sub.add_parser(name)
    report = sub.add_parser("analytics")
    report.add_argument("--target", choices=["local", "postgres"], default="local")
    importer = sub.add_parser("import")
    importer.add_argument("file", type=Path)
    importer.add_argument("--as-of", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("aquawatch.api:app", host="127.0.0.1", port=args.port)
        return
    fixture = generate()
    if args.command == "generate":
        target = Path("data/sample")
        target.mkdir(parents=True, exist_ok=True)
        (target / "baseline.csv").write_bytes(fixture["csv"])
        (target / "daily.csv").write_bytes(fixture["daily_csv"])
        (target / "labels.json").write_text(
            json.dumps(fixture["labels"], indent=2), encoding="utf-8"
        )
        print("Generated deterministic synthetic fixtures in data/sample")
        return
    engine = db.make_engine()
    bootstrap(engine, fixture)
    if args.command == "demo":
        print(
            json.dumps(
                ingest(engine, fixture["csv"], "synthetic-baseline.csv", AS_OF.isoformat()),
                indent=2,
            )
        )
    elif args.command == "import":
        print(
            json.dumps(ingest(engine, args.file.read_bytes(), args.file.name, args.as_of), indent=2)
        )
    elif args.command == "export-raw":
        export_raw(engine)
        print("Exported operational tables to dbt/seeds")
    elif args.command == "benchmark":
        from .benchmark import run_benchmark

        result = run_benchmark()
        Path("docs").mkdir(exist_ok=True)
        Path("docs/benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
    elif args.command == "analytics":
        export_raw(engine)
        env = {**os.environ, "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
        executable = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
        subprocess.run(
            [
                str(executable),
                "build",
                "--project-dir",
                "dbt",
                "--profiles-dir",
                "dbt",
                "--target",
                args.target,
            ],
            check=True,
            env=env,
        )
        subprocess.run(
            [
                str(executable),
                "docs",
                "generate",
                "--project-dir",
                "dbt",
                "--profiles-dir",
                "dbt",
                "--target",
                args.target,
            ],
            check=True,
            env=env,
        )
        from .reporting import export_marts

        export_marts(args.target)


if __name__ == "__main__":
    main()
