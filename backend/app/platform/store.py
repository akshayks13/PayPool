"""Transactional storage: SQLite for local runs, PostgreSQL via DATABASE_URL.

Domain documents have explicit kinds and immutable IDs. This compact MVP store
keeps the whole commerce transition in one transaction; a PostgreSQL advisory
lock serializes transitions across workers, not just threads in one process.
"""

import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Column,
    MetaData,
    String,
    Table,
    create_engine,
    select,
    text,
)

metadata = MetaData()
records = Table(
    "paypool_records",
    metadata,
    Column("kind", String(40), primary_key=True),
    Column("id", String(100), primary_key=True),
    Column("data", JSON, nullable=False),
)


def now():
    return datetime.now(UTC).isoformat()


class Transaction:
    def __init__(self, connection, postgis=False):
        self.connection = connection
        self.postgis = postgis

    def get(self, kind, key):
        row = self.connection.execute(
            select(records.c.data).where(
                records.c.kind == kind, records.c.id == str(key)
            )
        ).first()
        return dict(row[0]) if row else None

    def all(self, kind):
        return [
            dict(row[0])
            for row in self.connection.execute(
                select(records.c.data)
                .where(records.c.kind == kind)
                .order_by(records.c.id)
            )
        ]

    def put(self, kind, data):
        data = dict(data)
        key = str(data.setdefault("id", str(uuid4())))
        if self.get(kind, key):
            self.connection.execute(
                records.update()
                .where(records.c.kind == kind, records.c.id == key)
                .values(data=data)
            )
        else:
            self.connection.execute(
                records.insert().values(kind=kind, id=key, data=data)
            )
        if kind == "zones" and self.postgis:
            ring = list(data["polygon"])
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            geometry = json.dumps({"type": "Polygon", "coordinates": [ring]})
            valid = self.connection.execute(
                text("SELECT ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON(:g),4326))"),
                {"g": geometry},
            ).scalar()
            if not valid:
                raise ValueError("Delivery polygon is invalid")
            self.connection.execute(
                text(
                    "INSERT INTO paypool_geofences (id, service_polygon) VALUES (:id,ST_SetSRID(ST_GeomFromGeoJSON(:g),4326)) ON CONFLICT (id) DO UPDATE SET service_polygon=EXCLUDED.service_polygon"
                ),
                {"id": key, "g": geometry},
            )
        return data

    def covers(self, zone_id, point):
        return bool(
            self.connection.execute(
                text(
                    "SELECT ST_Covers(service_polygon,ST_SetSRID(ST_MakePoint(:lon,:lat),4326)) FROM paypool_geofences WHERE id=:id"
                ),
                {"id": zone_id, "lon": point[0], "lat": point[1]},
            ).scalar()
        )

    def delete(self, kind, key):
        self.connection.execute(
            records.delete().where(records.c.kind == kind, records.c.id == str(key))
        )

    def audit(self, actor, action, subject, details=None):
        event = self.put(
            "audit",
            {
                "id": str(uuid4()),
                "at": now(),
                "actor": actor,
                "action": action,
                "subject": subject,
                "details": details or {},
            },
        )
        self.put(
            "outbox",
            {
                "id": event["id"],
                "event_id": event["id"],
                "event_type": action.lower().replace("_", "."),
                "occurred_at": event["at"],
                "correlation_id": subject,
                "aggregate_id": subject,
                "schema_version": 1,
                "payload": {
                    "actor": actor,
                    "action": action,
                    "subject": subject,
                    "details": details or {},
                },
                "status": "PENDING",
                "attempts": 0,
                "next_attempt_at": event["at"],
            },
        )
        recipients = {actor}
        if action.startswith(("ROLE_", "ACCOUNT_", "SELLER_APPLICATION_")) and self.get(
            "users", subject
        ):
            recipients.add(subject)
        for kind in ("pools", "orders", "requests", "offers", "standing_orders"):
            record = self.get(kind, subject)
            if not record:
                continue
            recipients.update(
                str(record[k])
                for k in ("seller_id", "buyer_id", "driver_id")
                if record.get(k)
            )
            for request_id in record.get("request_ids", []):
                request = self.get("requests", request_id)
                if request:
                    recipients.add(request["buyer_id"])
        for user_id in recipients:
            recipient = self.get("users", user_id) or {}
            mandatory = action.startswith(
                (
                    "PAYMENT_",
                    "ROLE_",
                    "ACCOUNT_",
                    "PAYPAL_",
                    "POD_",
                    "BUYER_RECEIPT_",
                    "SELLER_APPLICATION_",
                )
            )
            if not recipient.get("notifications_in_app", True) and not mandatory:
                continue
            self.put(
                "notifications",
                {
                    "id": str(uuid4()),
                    "user_id": user_id,
                    "action": action,
                    "subject": subject,
                    "read": False,
                    "created_at": event["at"],
                },
            )
        return event


class Store:
    def __init__(self, url=None):
        url = url or os.getenv("DATABASE_URL", "sqlite:///./data/paypool.db")
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        if url.startswith("sqlite:///") and ":memory:" not in url:
            Path(url.removeprefix("sqlite:///")).parent.mkdir(
                parents=True, exist_ok=True
            )
        kwargs = (
            {"connect_args": {"check_same_thread": False, "timeout": 30}}
            if url.startswith("sqlite")
            else {}
        )
        if ":memory:" in url:
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
        self.engine = create_engine(url, **kwargs)
        if os.getenv("PAYPOOL_SCHEMA_AUTO_CREATE", "true").lower() == "true":
            metadata.create_all(self.engine)
        self.postgis = os.getenv("PAYPOOL_POSTGIS", "false").lower() == "true"
        if self.postgis:
            if self.engine.dialect.name != "postgresql":
                raise ValueError("PAYPOOL_POSTGIS requires a PostgreSQL DATABASE_URL")
            with self.engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS paypool_geofences (id TEXT PRIMARY KEY, service_polygon geometry(Polygon,4326) NOT NULL)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS paypool_geofences_gist ON paypool_geofences USING GIST(service_polygon)"
                    )
                )
        self.lock = RLock()
        if self.postgis:
            with self.transaction() as tx:
                for zone in tx.all("zones"):
                    tx.put("zones", zone)

    @contextmanager
    def transaction(self):
        with self.lock, self.engine.connect() as conn:
            if self.engine.dialect.name == "sqlite":
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                conn.begin()
                conn.execute(text("SELECT pg_advisory_xact_lock(734492001)"))
            try:
                yield Transaction(conn, self.postgis)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
