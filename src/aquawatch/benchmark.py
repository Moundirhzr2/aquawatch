"""Run rules against held-out deterministic seeds in temporary databases."""

import platform
import tempfile
import time
from pathlib import Path

from . import db
from .evaluation import evaluate
from .pipeline import bootstrap, ingest, records
from .synthetic import AS_OF, generate


def run_benchmark(seeds=(42, 71, 103)):
    results = []
    with tempfile.TemporaryDirectory(prefix="aquawatch-benchmark-") as folder:
        for seed in seeds:
            engine = db.make_engine(f"sqlite:///{(Path(folder) / f'{seed}.sqlite').as_posix()}")
            fixture = generate(seed)
            bootstrap(engine, fixture)
            started = time.perf_counter()
            run = ingest(engine, fixture["csv"], f"seed-{seed}.csv", AS_OF.isoformat())
            duration = time.perf_counter() - started
            with engine.connect() as conn:
                result = evaluate(records(conn, db.cases), fixture["labels"])
            results.append(
                {
                    "seed": seed,
                    "seconds": round(duration, 3),
                    "accepted_rows": run["accepted"],
                    "quarantined_rows": run["rejected"],
                    **result,
                }
            )
            engine.dispose()
    return {
        "python": platform.python_version(),
        "platform": platform.system(),
        "method": "Seed 42 demonstration; seeds 71 and 103 vary consumption only, not event templates. No independent field validation.",
        "runs": results,
    }
