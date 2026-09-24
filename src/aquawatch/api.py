"""Same-origin local demo API. No real customer data or public-write deployment."""

from __future__ import annotations

import csv
import io
import os
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import db
from .detection import series
from .evaluation import evaluate
from .pipeline import (
    MAX_BYTES,
    ImportInProgressError,
    bootstrap,
    ingest,
    now,
    records,
    recover_stale_runs,
)
from .reconciliation import reconcile_invoice
from .synthetic import AS_OF, generate

STATIC = Path(__file__).parent / "static"


class CaseUpdate(BaseModel):
    status: Literal["open", "investigating", "resolved", "dismissed"]
    note: str = Field(min_length=5, max_length=1000)
    version: int = Field(ge=1)

    @field_validator("note")
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Please provide an investigation note of at least 5 characters.")
        return value


def create_app(engine=None, auto_seed=True):
    engine = engine or db.make_engine()
    fixture = generate()
    lock = threading.Lock()
    csrf = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(_app):
        db.metadata.create_all(engine)
        recover_stale_runs(engine)
        if auto_seed:
            bootstrap(engine, fixture)
            ingest(engine, fixture["csv"], "synthetic-baseline.csv", AS_OF.isoformat())
        yield

    app = FastAPI(
        title="AquaWatch API",
        version="1.0.0",
        lifespan=lifespan,
        description="Synthetic portfolio demonstration. Local single-operator mode.",
    )
    app.state.engine = engine
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(","),
    )

    @app.middleware("http")
    async def protect(request: Request, call_next):
        if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            token = request.headers.get("x-aquawatch-token", "")
            if not token.isascii() or not secrets.compare_digest(token, csrf):
                return JSONResponse(
                    {"detail": "Missing or invalid session token. Reload the page."},
                    status_code=403,
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.url.path in {"/docs", "/redoc"}:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'"
            )
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/session")
    def session():
        return {"token": csrf, "mode": "synthetic-local-demo", "actor": "Local demo operator"}

    @app.get("/health")
    def health():
        with engine.connect() as conn:
            conn.execute(select(func.count()).select_from(db.meters))
        return {"status": "ok", "database": engine.dialect.name}

    @app.get("/api/overview")
    def overview():
        with engine.connect() as conn:
            read = records(conn, db.readings)
            case_rows = records(conn, db.cases)
            run_rows = records(conn, db.runs)
            total_meters = conn.execute(select(func.count()).select_from(db.meters)).scalar_one()
            customers = {r["id"]: r for r in records(conn, db.customers)}
            meter_map = {r["id"]: customers[r["customer_id"]] for r in records(conn, db.meters)}
        grouped = {}
        for row in read:
            grouped.setdefault(row["meter_id"], []).append(row)
        daily = {}
        for mid, rows in grouped.items():
            for row in series(rows):
                item = daily.setdefault(
                    row["reading_date"],
                    {"date": row["reading_date"], "liters": 0, "valid_intervals": 0},
                )
                if row["consumption_liters"] is not None:
                    item["liters"] += row["consumption_liters"]
                    item["valid_intervals"] += 1
        active = [r for r in case_rows if r["status"] in {"open", "investigating"}]
        rejected = sum(r["rejected"] for r in run_rows)
        accepted = sum(r["accepted"] for r in run_rows)
        quality = 100 * accepted / (accepted + rejected) if accepted + rejected else 0
        return dict(
            meters=total_meters,
            readings=len(read),
            active_cases=len(active),
            review_amount_cents=sum(r["amount_cents"] for r in active),
            quality_rate=round(quality, 2),
            rejected_rows=rejected,
            as_of=max(daily, default=None),
            daily=[daily[k] for k in sorted(daily)],
            kinds=[
                {"kind": k, "count": sum(r["kind"] == k for r in active)}
                for k in sorted({r["kind"] for r in case_rows})
            ],
            districts=[
                {
                    "district": d,
                    "cases": sum(meter_map[r["meter_id"]]["district"] == d for r in active),
                }
                for d in sorted({r["district"] for r in customers.values()})
            ],
            latest_run=max(run_rows, key=lambda r: r["started_at"], default=None),
        )

    @app.get("/api/cases")
    def list_cases(status: str = "all", kind: str = "all", q: str = ""):
        with engine.connect() as conn:
            query = (
                select(
                    db.cases,
                    db.customers.c.name.label("customer_name"),
                    db.customers.c.district,
                    db.customers.c.segment,
                )
                .join(db.meters, db.meters.c.id == db.cases.c.meter_id)
                .join(db.customers, db.customers.c.id == db.meters.c.customer_id)
            )
            if status == "active":
                query = query.where(db.cases.c.status.in_(["open", "investigating"]))
            elif status != "all":
                query = query.where(db.cases.c.status == status)
            if kind != "all":
                query = query.where(db.cases.c.kind == kind)
            rows = [dict(r) for r in conn.execute(query).mappings()]
        if q:
            needle = q.lower()[:100]
            rows = [
                r
                for r in rows
                if needle
                in f"{r['meter_id']} {r['title']} {r['customer_name']} {r['district']}".lower()
            ]
        return sorted(
            rows, key=lambda r: (r["severity"] != "high", -r["amount_cents"], r["meter_id"])
        )

    @app.get("/api/cases/{case_id}")
    def detail(case_id: str):
        with engine.connect() as conn:
            item = conn.execute(select(db.cases).where(db.cases.c.id == case_id)).mappings().first()
            if item is None:
                raise HTTPException(404, "Case not found")
            timeline = list(
                conn.execute(
                    select(db.readings).where(db.readings.c.meter_id == item["meter_id"])
                ).mappings()
            )
            events = list(
                conn.execute(
                    select(db.history)
                    .where(db.history.c.case_id == case_id)
                    .order_by(db.history.c.at)
                ).mappings()
            )
        return {**item, "readings": series(timeline), "history": [dict(r) for r in events]}

    @app.get("/api/billing/reconciliation")
    def billing_reconciliation():
        with engine.connect() as conn:
            invoices = records(conn, db.invoices)
            readings = records(conn, db.readings)
            meters = {r["id"]: r for r in records(conn, db.meters)}
            customers = {r["id"]: r for r in records(conn, db.customers)}
            cases = {
                (r["meter_id"], r["event_date"]): r["id"]
                for r in records(conn, db.cases)
                if r["kind"] == "volume_mismatch"
            }
        by_meter = {}
        for row in readings:
            by_meter.setdefault(row["meter_id"], []).append(row)
        return [
            {
                "invoice_id": invoice["id"],
                "meter_id": invoice["meter_id"],
                "district": customers[meters[invoice["meter_id"]]["customer_id"]]["district"],
                "period_start": invoice["period_start"],
                "period_end": invoice["period_end"],
                "billed_volume_liters": invoice["billed_volume_liters"],
                "case_id": cases.get((invoice["meter_id"], invoice["period_end"])),
                **reconcile_invoice(invoice, by_meter.get(invoice["meter_id"], [])),
            }
            for invoice in invoices
        ]

    @app.patch("/api/cases/{case_id}")
    def change_case(case_id: str, payload: CaseUpdate):
        transitions = {
            "open": {"investigating", "dismissed"},
            "investigating": {"resolved", "dismissed", "open"},
            "resolved": {"open"},
            "dismissed": {"open"},
        }
        with lock, engine.begin() as conn:
            current = (
                conn.execute(select(db.cases).where(db.cases.c.id == case_id)).mappings().first()
            )
            if not current:
                raise HTTPException(404, "Case not found")
            if current["version"] != payload.version:
                raise HTTPException(409, "Case changed in another session. Refresh before saving.")
            if payload.status not in transitions[current["status"]]:
                raise HTTPException(
                    422, "Invalid status transition. Start investigating before resolving."
                )
            result = conn.execute(
                update(db.cases)
                .where(db.cases.c.id == case_id, db.cases.c.version == payload.version)
                .values(status=payload.status, version=payload.version + 1)
            )
            if result.rowcount != 1:
                raise HTTPException(409, "Case changed in another session.")
            conn.execute(
                db.history.insert().values(
                    id=str(uuid4()),
                    case_id=case_id,
                    at=now(),
                    actor="Local demo operator",
                    from_status=current["status"],
                    to_status=payload.status,
                    note=payload.note,
                )
            )
        return {"id": case_id, "status": payload.status, "version": payload.version + 1}

    @app.get("/api/runs")
    def list_runs():
        with engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    select(db.runs).order_by(db.runs.c.started_at.desc())
                ).mappings()
            ]

    @app.get("/api/ingestion/health")
    def ingestion_health():
        with engine.connect() as conn:
            counts = {
                status: conn.execute(
                    select(func.count()).select_from(db.runs).where(db.runs.c.status == status)
                ).scalar_one()
                for status in ("completed", "failed", "running")
            }
            latest_completed = conn.execute(
                select(func.max(db.runs.c.finished_at)).where(db.runs.c.status == "completed")
            ).scalar_one_or_none()
            latest_reading = conn.execute(
                select(func.max(db.readings.c.reading_date))
            ).scalar_one_or_none()
        return {
            "run_counts": counts,
            "latest_completed_at": latest_completed,
            "latest_reading_date": latest_reading,
            "reading_age_days": (date.today() - date.fromisoformat(latest_reading)).days
            if latest_reading
            else None,
            "data_kind": "synthetic_demo",
        }

    @app.get("/api/runs/{run_id}/rejections")
    def rejected_rows(run_id: str):
        with engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    select(db.rejections).where(db.rejections.c.run_id == run_id)
                ).mappings()
            ]

    @app.post("/api/import/demo")
    def daily_import():
        try:
            with lock:
                result = ingest(
                    engine,
                    fixture["daily_csv"],
                    "synthetic-daily.csv",
                    (AS_OF + timedelta(days=1)).isoformat(),
                )
        except ImportInProgressError as exc:
            raise HTTPException(409, str(exc)) from exc
        return result

    @app.post("/api/import")
    async def upload(file: UploadFile, as_of: date):
        content = await file.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise HTTPException(413, "CSV exceeds the 5 MB limit")
        with engine.connect() as conn:
            latest = conn.execute(select(func.max(db.readings.c.reading_date))).scalar_one_or_none()
        if latest and as_of.isoformat() < latest:
            raise HTTPException(422, "As-of date cannot precede the latest stored reading.")
        try:
            with lock:
                return ingest(
                    engine, content, Path(file.filename or "upload.csv").name, as_of.isoformat()
                )
        except ImportInProgressError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/evaluation")
    def evaluation():
        # Evaluate a separate reproducible fixture, so user imports/decisions cannot alter the benchmark.
        import csv as csv_module

        from .detection import case, detect

        clean, seen, duplicate_cases = [], {}, []
        for row in csv_module.DictReader(io.StringIO(fixture["csv"].decode())):
            if row["meter_id"] not in {m["id"] for m in fixture["meters"]}:
                continue
            try:
                date.fromisoformat(row["reading_date"])
                row["counter_liters"] = int(row["counter_liters"])
                if row["counter_liters"] < 0:
                    continue
            except ValueError:
                continue
            key = (row["meter_id"], row["reading_date"])
            if key in seen:
                duplicate_cases.append(
                    case(
                        row["meter_id"],
                        "duplicate_reading",
                        row["reading_date"],
                        "medium",
                        "",
                        "",
                        {},
                    )
                )
            else:
                seen[key] = True
                clean.append(row)
        predictions = (
            detect(clean, fixture["invoices"], fixture["tariffs"], AS_OF.isoformat())
            + duplicate_cases
        )
        return evaluate(predictions, fixture["labels"])

    @app.get("/api/export/cases.csv")
    def export_cases():
        fields = [
            "id",
            "meter_id",
            "kind",
            "event_date",
            "severity",
            "status",
            "amount_cents",
            "title",
        ]
        with engine.connect() as conn:
            rows = records(conn, db.cases)
        out = io.StringIO(newline="")
        writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: ("'" + v if isinstance(v, str) and v[:1] in {"=", "+", "-", "@"} else v)
                    for k, v in row.items()
                }
            )
        return Response(
            out.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="aquawatch-cases.csv"'},
        )

    @app.get("/api/sample.csv")
    def sample():
        return Response(
            fixture["daily_csv"],
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="sample-daily.csv"'},
        )

    @app.get("/")
    def root():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
