"""Portable operational schema. Store money in cents and counters in integer liters."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)

metadata = MetaData()
customers = Table(
    "customers",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("name", String(120), nullable=False),
    Column("district", String(80), nullable=False),
    Column("segment", String(40), nullable=False),
)
meters = Table(
    "meters",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("customer_id", ForeignKey("customers.id"), nullable=False),
    Column("installed_on", String(10), nullable=False),
)
tariffs = Table(
    "tariffs",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("rate_cents_per_m3", Integer, nullable=False),
    Column("fixed_fee_cents", Integer, nullable=False),
    CheckConstraint("rate_cents_per_m3 >= 0 AND fixed_fee_cents >= 0"),
)
invoices = Table(
    "invoices",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("meter_id", ForeignKey("meters.id"), nullable=False),
    Column("tariff_id", ForeignKey("tariffs.id"), nullable=False),
    Column("period_start", String(10), nullable=False),
    Column("period_end", String(10), nullable=False),
    Column("billed_volume_liters", Integer, nullable=False),
    Column("billed_amount_cents", Integer, nullable=False),
    CheckConstraint("billed_volume_liters >= 0 AND billed_amount_cents >= 0"),
)
runs = Table(
    "ingestion_runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("file_name", String(160), nullable=False),
    Column("sha256", String(64), unique=True, nullable=False),
    Column("started_at", String(40), nullable=False),
    Column("finished_at", String(40)),
    Column("status", String(20), nullable=False),
    Column("accepted", Integer, nullable=False, default=0),
    Column("rejected", Integer, nullable=False, default=0),
    Column("duplicates", Integer, nullable=False, default=0),
    Column("error", Text),
)
readings = Table(
    "readings",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("meter_id", ForeignKey("meters.id"), nullable=False),
    Column("reading_date", String(10), nullable=False),
    Column("counter_liters", Integer, nullable=False),
    Column("run_id", ForeignKey("ingestion_runs.id"), nullable=False),
    UniqueConstraint("meter_id", "reading_date"),
    CheckConstraint("counter_liters >= 0"),
)
Index("ix_readings_meter_date", readings.c.meter_id, readings.c.reading_date)
rejections = Table(
    "rejections",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("run_id", ForeignKey("ingestion_runs.id"), nullable=False),
    Column("row_number", Integer, nullable=False),
    Column("reason", String(80), nullable=False),
    Column("payload", JSON, nullable=False),
)
cases = Table(
    "cases",
    metadata,
    Column("id", String(24), primary_key=True),
    Column("meter_id", ForeignKey("meters.id"), nullable=False),
    Column("kind", String(40), nullable=False),
    Column("event_date", String(10), nullable=False),
    Column("severity", String(12), nullable=False),
    Column("title", String(140), nullable=False),
    Column("explanation", Text, nullable=False),
    Column("evidence", JSON, nullable=False),
    Column("amount_cents", Integer, nullable=False, default=0),
    Column("status", String(20), nullable=False, default="open"),
    Column("version", Integer, nullable=False, default=1),
    Column("created_at", String(40), nullable=False),
    CheckConstraint("status IN ('open', 'investigating', 'resolved', 'dismissed')"),
    UniqueConstraint("meter_id", "kind", "event_date"),
)
history = Table(
    "case_history",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("case_id", ForeignKey("cases.id"), nullable=False),
    Column("at", String(40), nullable=False),
    Column("actor", String(80), nullable=False),
    Column("from_status", String(20), nullable=False),
    Column("to_status", String(20), nullable=False),
    Column("note", Text, nullable=False),
)


def make_engine(url: str | None = None):
    if url is None:
        Path("runtime").mkdir(exist_ok=True)
        url = os.getenv("DATABASE_URL", "sqlite:///runtime/aquawatch.sqlite")
    options = (
        {"connect_args": {"check_same_thread": False, "timeout": 30}}
        if url.startswith("sqlite")
        else {}
    )
    engine = create_engine(url, pool_pre_ping=True, **options)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def sqlite_pragmas(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")

    return engine
