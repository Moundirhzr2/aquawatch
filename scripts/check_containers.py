"""Exercise the real Compose stack using an isolated, disposable project."""

import argparse
import csv
import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def available_ports():
    # Keep both sockets reserved until both distinct ports have been selected.
    with socket.socket() as app, socket.socket() as db:
        app.bind(("127.0.0.1", 0))
        db.bind(("127.0.0.1", 0))
        return app.getsockname()[1], db.getsockname()[1]


def check(config_only=False):
    # The executable is fixed; CLI input must never select a program to run.
    # As with other developer tools, Docker must be installed on a trusted PATH.
    docker = "docker"
    subprocess.run([docker, "compose", "version"], check=True, timeout=30)
    if not config_only:
        subprocess.run([docker, "info", "--format", "{{.OSType}}"], check=True, timeout=30)
    runtime = ROOT / "runtime"
    runtime.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="container-check-", dir=runtime) as directory:
        temporary = Path(directory).resolve()
        assert temporary.is_relative_to(runtime.resolve())
        exports = temporary / "exports"
        exports.mkdir(mode=0o777)
        exports.chmod(0o777)  # The Linux image runs as UID 10001.
        override = temporary / "compose.json"
        override.write_text(
            json.dumps(
                {
                    "services": {
                        "analytics": {"volumes": [f"{exports.as_posix()}:/app/powerbi/data"]}
                    }
                }
            ),
            encoding="utf-8",
        )
        empty_env = temporary / ".env"
        empty_env.write_text("", encoding="utf-8")
        app_port, db_port = available_ports()
        environment = os.environ.copy()
        environment.update(
            POSTGRES_USER="aquawatch",
            POSTGRES_DB="aquawatch",
            POSTGRES_PASSWORD=secrets.token_hex(24),
            AQUAWATCH_APP_PORT=str(app_port),
            AQUAWATCH_DB_PORT=str(db_port),
        )
        compose = [
            docker,
            "compose",
            "--project-directory",
            str(ROOT),
            "--env-file",
            str(empty_env),
            "--project-name",
            f"aquawatch-check-{uuid4().hex[:12]}",
            "--file",
            str(ROOT / "compose.yaml"),
            "--file",
            str(override),
        ]

        def run(*arguments, timeout=1200):
            subprocess.run(compose + list(arguments), env=environment, check=True, timeout=timeout)

        run("--profile", "analytics", "config", "--quiet", timeout=30)
        if config_only:
            print("Compose configuration validated. Containers were not started.")
            return

        base = f"http://127.0.0.1:{app_port}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def request(path, payload=None, token=None):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["x-aquawatch-token"] = token
            req = urllib.request.Request(
                base + path,
                data=json.dumps(payload).encode() if payload else None,
                headers=headers,
                method="PATCH" if payload else "GET",
            )
            with opener.open(req, timeout=10) as response:
                return json.load(response)

        def wait_healthy():
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    if request("/health") == {"status": "ok", "database": "postgresql"}:
                        return
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(1)
            raise RuntimeError("Container API did not become healthy on PostgreSQL")

        try:
            run("up", "--build", "--detach", "--wait", "--wait-timeout", "180", "app")
            wait_healthy()
            overview = request("/api/overview")
            assert overview["meters"] == 120 and overview["readings"] == 10796, overview
            runs = request("/api/runs")
            case = request("/api/cases?status=open")[0]
            token = request("/api/session")["token"]
            note = "Container verification: decision must survive an app restart."
            request(
                f"/api/cases/{case['id']}",
                {"status": "investigating", "version": case["version"], "note": note},
                token,
            )
            with opener.open(base + "/", timeout=10) as page:
                assert "AquaWatch" in page.read().decode()
            run("restart", "app", timeout=60)
            wait_healthy()
            persisted = request(f"/api/cases/{case['id']}")
            assert persisted["status"] == "investigating", persisted
            assert any(event["note"] == note for event in persisted["history"]), persisted
            assert request("/api/runs") == runs, "Restart unexpectedly added an ingestion run"
            assert request("/api/overview")["readings"] == overview["readings"]
            run("--profile", "analytics", "run", "--build", "--rm", "analytics")
            run(
                "--profile",
                "analytics",
                "run",
                "--rm",
                "analytics",
                "python",
                "scripts/check_analytics.py",
                "--target",
                "postgres",
            )
            expected = {
                "dim_date",
                "dim_meters",
                "fct_consumption",
                "fct_billing",
                "fct_cases",
                "fct_imports",
                "network_daily",
            }
            assert {path.stem for path in exports.glob("*.csv")} == expected
            for path in exports.glob("*.csv"):
                with path.open(encoding="utf-8", newline="") as handle:
                    assert next(csv.DictReader(handle), None), f"Empty export: {path.name}"
            print(
                "Container checks passed: PostgreSQL API, persistent decisions, replay on restart, dbt, SQL parity and seven CSV exports."
            )
        except Exception:
            subprocess.run(compose + ["logs", "--tail", "80"], env=environment, timeout=30)
            raise
        finally:
            # Only this invocation's random project and its newly created volumes.
            run("down", "--volumes", "--remove-orphans", timeout=90)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "--config-only", action="store_true", help="Validate Compose without a daemon"
    )
    args = parser.parse_args(argv)
    check(config_only=args.config_only)


if __name__ == "__main__":
    main()
