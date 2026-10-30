from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "medguard.sqlite3"
SEED_PATH = BASE_DIR / "data" / "demo_data.json"

DEFAULT_SETTINGS = {
    "critical_days": "3",
    "warning_days": "7",
    "llm_provider": "deterministic",
    "ollama_base_url": "http://localhost:11434",
    "ollama_model": "llama3.2",
}

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS hospitals (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL, state TEXT NOT NULL, type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS medicines (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, unit TEXT NOT NULL, criticality TEXT NOT NULL,
  primary_supplier_id TEXT, manufacture_date TEXT, expiry_date TEXT
);
CREATE TABLE IF NOT EXISTS inventory (
  hospital_id TEXT NOT NULL, medicine_id TEXT NOT NULL, current_stock REAL NOT NULL,
  daily_demand REAL, safety_stock REAL NOT NULL, updated_at TEXT NOT NULL,
  PRIMARY KEY (hospital_id, medicine_id)
);
CREATE TABLE IF NOT EXISTS sales_transactions (
  id TEXT PRIMARY KEY, hospital_id TEXT NOT NULL, medicine_id TEXT NOT NULL,
  quantity REAL NOT NULL, sold_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS suppliers (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL, reliability REAL NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS supplier_medicines (
  supplier_id TEXT NOT NULL, medicine_id TEXT NOT NULL, unit_price REAL NOT NULL,
  available_qty REAL NOT NULL, lead_days REAL NOT NULL,
  PRIMARY KEY (supplier_id, medicine_id)
);
CREATE TABLE IF NOT EXISTS disruptions (
  id TEXT PRIMARY KEY, event_type TEXT NOT NULL, severity TEXT NOT NULL, title TEXT NOT NULL,
  summary TEXT NOT NULL, hospital_id TEXT NOT NULL, medicine_id TEXT NOT NULL,
  impact_days REAL, status TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recommendations (
  id TEXT PRIMARY KEY, disruption_id TEXT NOT NULL, recommendation_type TEXT NOT NULL,
  hospital_id TEXT NOT NULL, donor_hospital_id TEXT, supplier_id TEXT, medicine_id TEXT NOT NULL,
  quantity REAL NOT NULL, reason TEXT NOT NULL, benefit TEXT NOT NULL, risk TEXT NOT NULL,
  status TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY, recommendation_id TEXT NOT NULL, decision TEXT NOT NULL,
  reviewer TEXT, reason TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shipments (
  id TEXT PRIMARY KEY, recommendation_id TEXT, source_type TEXT NOT NULL, source_id TEXT,
  source_label TEXT NOT NULL, destination_id TEXT NOT NULL, medicine_id TEXT NOT NULL,
  quantity REAL NOT NULL, status TEXT NOT NULL, eta_hours REAL NOT NULL,
  expected_arrival TEXT, route_json TEXT NOT NULL, created_at TEXT NOT NULL, delivered_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_events (
  id TEXT PRIMARY KEY, event_type TEXT NOT NULL, actor TEXT NOT NULL,
  entity_type TEXT, entity_id TEXT, summary TEXT NOT NULL,
  details_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return prefix + "-" + uuid.uuid4().hex[:10].upper()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH, timeout=8)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 8000")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def record_audit(
    connection: sqlite3.Connection,
    event_type: str,
    actor: str,
    summary: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict | None = None,
) -> str:
    event_id = new_id("EVT")
    connection.execute(
        """INSERT INTO audit_events
           (id,event_type,actor,entity_type,entity_id,summary,details_json,created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (event_id, event_type, actor, entity_type, entity_id, summary,
         json.dumps(details or {}, ensure_ascii=False), now_iso()),
    )
    return event_id


def _load_seed() -> dict:
    with SEED_PATH.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def _seed_dataset(connection: sqlite3.Connection) -> None:
    data = _load_seed()
    connection.executemany(
        "INSERT INTO hospitals(id,name,city,state,type) VALUES (?,?,?,?,?)",
        [(h["id"], h["name"], h["city"], h["state"], h["type"]) for h in data["hospitals"]],
    )
    connection.executemany(
        """INSERT INTO medicines(id,name,unit,criticality,primary_supplier_id,manufacture_date,expiry_date)
           VALUES (?,?,?,?,?,?,?)""",
        [(m["id"], m["name"], m["unit"], m["criticality"], m["primary_supplier_id"],
          (datetime.now(timezone.utc)-timedelta(days=120)).date().isoformat(),
          (datetime.now(timezone.utc)+timedelta(days=540+(index*90))).date().isoformat())
         for index,m in enumerate(data["medicines"])],
    )
    stamp = now_iso()
    connection.executemany(
        """INSERT INTO inventory(hospital_id,medicine_id,current_stock,daily_demand,safety_stock,updated_at)
           VALUES (?,?,?,?,?,?)""",
        [(row[0], row[1], row[2], row[3], row[4], stamp) for row in data["inventory"]],
    )
    connection.executemany(
        "INSERT INTO suppliers(id,name,city,reliability,status) VALUES (?,?,?,?,?)",
        [(s["id"], s["name"], s["city"], s["reliability"], s["status"]) for s in data["suppliers"]],
    )
    connection.executemany(
        """INSERT INTO supplier_medicines(supplier_id,medicine_id,unit_price,available_qty,lead_days)
           VALUES (?,?,?,?,?)""",
        data["supplier_medicines"],
    )
    for item in data["shipments"]:
        eta = float(item["eta_hours"])
        expected = (datetime.now(timezone.utc) + timedelta(hours=eta)).isoformat(timespec="seconds").replace("+00:00", "Z") if item["status"] != "Delivered" else now_iso()
        connection.execute(
            """INSERT INTO shipments
               (id,recommendation_id,source_type,source_id,source_label,destination_id,medicine_id,
                quantity,status,eta_hours,expected_arrival,route_json,created_at,delivered_at)
               VALUES (?,NULL,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (item["id"], item["source_type"], item["source_id"], item["source_label"],
             item["destination_id"], item["medicine_id"], item["quantity"], item["status"],
             eta, expected, json.dumps(item["route"]), stamp, now_iso() if item["status"] == "Delivered" else None),
        )
    for key, value in DEFAULT_SETTINGS.items():
        connection.execute("INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)", (key, value))


def initialize() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.executescript(SCHEMA)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(medicines)")}
        if "manufacture_date" not in columns:
            connection.execute("ALTER TABLE medicines ADD COLUMN manufacture_date TEXT")
        if "expiry_date" not in columns:
            connection.execute("ALTER TABLE medicines ADD COLUMN expiry_date TEXT")
        connection.execute("UPDATE medicines SET manufacture_date=COALESCE(manufacture_date,date('now','-120 day')), expiry_date=COALESCE(expiry_date,date('now','+540 day'))")
        count = connection.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0]
        if count == 0:
            _seed_dataset(connection)
            record_audit(
                connection, "system.seeded", "MedGuard demo",
                "Loaded the fictional five-hospital medicine dataset.",
                "dataset", "demo-data",
                {"hospitals": 5, "medicines": 5, "supplier_count": 4, "simulated": True},
            )


def reset_demo() -> None:
    with connect() as connection:
        for table in ("approvals", "recommendations", "shipments", "sales_transactions", "disruptions", "audit_events",
                      "inventory", "supplier_medicines", "suppliers", "medicines", "hospitals", "settings"):
            connection.execute("DELETE FROM " + table)
        _seed_dataset(connection)
        record_audit(
            connection, "demo.reset", "Demo operator",
            "Reset scenario, stock, shipments, settings, and event history to the deterministic baseline.",
            "dataset", "demo-data", {"simulated": True},
        )


def get_settings(connection: sqlite3.Connection) -> dict:
    values = dict(connection.execute("SELECT key,value FROM settings").fetchall())
    for key, value in DEFAULT_SETTINGS.items():
        values.setdefault(key, value)
    return values


def set_setting(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        """INSERT INTO settings(key,value) VALUES (?,?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
        (key, value),
    )
