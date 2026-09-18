"""Transactional CSV ingestion, quarantine, provenance and stable investigation IDs."""

from __future__ import annotations

import csv
import hashlib
import io
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update

from . import db
from .detection import case, detect

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 100_000
FIELDS = ["meter_id", "reading_date", "counter_liters"]


def now():
    return datetime.now(timezone.utc).isoformat()


def records(conn, table):
    return [dict(r) for r in conn.execute(select(table)).mappings()]


def save_cases(conn, candidates):
    existing = set(conn.execute(select(db.cases.c.id)).scalars())
    added = 0
    for item in candidates:
        if item["id"] in existing:
            # Evidence can mature on later imports; human decisions must survive reruns.
            conn.execute(
                update(db.cases)
                .where(db.cases.c.id == item["id"])
                .values(explanation=item["explanation"], evidence=item["evidence"])
            )
            continue
        conn.execute(db.cases.insert().values(**item, status="open", version=1, created_at=now()))
        existing.add(item["id"])
        added += 1
    return added


def ingest(engine, content: bytes, filename: str, as_of: str) -> dict:
    if len(content) > MAX_BYTES:
        raise ValueError("CSV exceeds the 5 MB limit.")
    date.fromisoformat(as_of)
    digest = hashlib.sha256(content).hexdigest()
    with engine.connect() as conn:
        prior = conn.execute(select(db.runs).where(db.runs.c.sha256 == digest)).mappings().first()
        if prior:
            return {**prior, "replayed": True, "cases_added": 0}
    run_id = str(uuid4())
    run = dict(
        id=run_id,
        file_name=filename[:160],
        sha256=digest,
        started_at=now(),
        status="running",
        accepted=0,
        rejected=0,
        duplicates=0,
    )
    with engine.begin() as conn:
        conn.execute(db.runs.insert().values(**run))
    try:
        decoded = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded, newline=""), strict=True)
        if reader.fieldnames != FIELDS:
            raise ValueError("CSV header must be: meter_id,reading_date,counter_liters")
        with engine.begin() as conn:
            known_meters = set(conn.execute(select(db.meters.c.id)).scalars())
            existing = {r["id"]: r["counter_liters"] for r in records(conn, db.readings)}
            accepted, rejected, duplicates = [], [], []
            seen_rows = 0
            for row_number, row in enumerate(reader, 2):
                seen_rows += 1
                if seen_rows > MAX_ROWS:
                    raise ValueError("CSV exceeds the 100,000 row limit.")
                reason = None
                mid, day, counter = (
                    row.get("meter_id"),
                    row.get("reading_date"),
                    row.get("counter_liters"),
                )
                try:
                    if set(row) != set(FIELDS) or None in row.values():
                        raise ValueError("invalid_columns")
                    if mid not in known_meters:
                        raise ValueError("unknown_meter")
                    if not day or date.fromisoformat(day).isoformat() != day or day > as_of:
                        raise ValueError("invalid_or_future_date")
                    if not counter or not counter.isascii() or not counter.isdecimal():
                        raise ValueError("invalid_counter")
                    value = int(counter)
                    if value > 2_000_000_000:
                        raise ValueError("counter_out_of_range")
                    key = f"{mid}:{day}"
                    if key in existing:
                        reason = (
                            "duplicate_reading" if existing[key] == value else "conflicting_reading"
                        )
                        duplicates.append(
                            case(
                                mid,
                                "duplicate_reading",
                                day,
                                "medium",
                                "Duplicate or conflicting reading",
                                "Another record already exists for this meter and date. The original is retained and the incoming row is quarantined.",
                                dict(
                                    existing_counter_liters=existing[key],
                                    incoming_counter_liters=value,
                                    reason=reason,
                                ),
                            )
                        )
                    else:
                        accepted.append(
                            dict(
                                id=key,
                                meter_id=mid,
                                reading_date=day,
                                counter_liters=value,
                                run_id=run_id,
                            )
                        )
                        existing[key] = value
                except (ValueError, TypeError) as exc:
                    reason = (
                        str(exc)
                        if str(exc)
                        in {
                            "invalid_columns",
                            "unknown_meter",
                            "invalid_or_future_date",
                            "invalid_counter",
                            "counter_out_of_range",
                        }
                        else "invalid_or_future_date"
                    )
                if reason:
                    rejected.append(
                        dict(
                            id=str(uuid4()),
                            run_id=run_id,
                            row_number=row_number,
                            reason=reason,
                            payload={str(k): v for k, v in row.items()},
                        )
                    )
            if seen_rows == 0:
                raise ValueError("CSV contains no data rows.")
            if accepted:
                conn.execute(db.readings.insert(), accepted)
            if rejected:
                conn.execute(db.rejections.insert(), rejected)
            candidates = detect(
                records(conn, db.readings),
                records(conn, db.invoices),
                records(conn, db.tariffs),
                as_of,
            )
            added = save_cases(conn, candidates + duplicates)
            values = dict(
                status="completed",
                accepted=len(accepted),
                rejected=len(rejected),
                duplicates=len(duplicates),
                finished_at=now(),
            )
            conn.execute(update(db.runs).where(db.runs.c.id == run_id).values(**values))
        return {**run, **values, "replayed": False, "cases_added": added}
    except Exception as exc:
        # The entire batch rolls back; the failure ledger survives in another transaction.
        message = (
            str(exc)
            if isinstance(exc, (ValueError, UnicodeError, csv.Error))
            else "Database transaction failed; inspect server logs."
        )
        with engine.begin() as conn:
            conn.execute(
                update(db.runs)
                .where(db.runs.c.id == run_id)
                .values(status="failed", error=message[:500], finished_at=now())
            )
        raise ValueError(message) from exc


def bootstrap(engine, fixture):
    db.metadata.create_all(engine)
    with engine.begin() as conn:
        if conn.execute(select(db.customers.c.id).limit(1)).first():
            return
        for name in ["customers", "meters", "tariffs", "invoices"]:
            conn.execute(getattr(db, name).insert(), fixture[name])
