"""Deterministic disruption sensing agent. Every alert is a fictional demo event."""

from __future__ import annotations

import json
import sqlite3

from backend.db import new_id, now_iso, record_audit
from backend.agents.planning import days_of_stock

SCENARIOS = {
    "supplier_delay": {
        "title": "Deccan MedSupply replenishment delayed",
        "summary": "The regular norepinephrine delivery to Aster General is now expected in 5 days. This is simulated demo data.",
        "impact_days": 5.0,
        "demand_multiplier": 1.0,
        "uncertain": False,
    },
    "supplier_failure": {
        "title": "Deccan MedSupply shipment unavailable",
        "summary": "The regular norepinephrine supplier is unavailable. A 7-day fallback horizon is used for planning and is marked uncertain.",
        "impact_days": 7.0,
        "demand_multiplier": 1.0,
        "uncertain": True,
    },
    "demand_spike": {
        "title": "Norepinephrine demand spike at Aster General",
        "summary": "A simulated 50% increase in daily norepinephrine demand has been detected at Aster General.",
        "impact_days": 2.0,
        "demand_multiplier": 1.5,
        "uncertain": False,
    },
}


def detect(connection: sqlite3.Connection, scenario_key: str) -> dict:
    if scenario_key not in SCENARIOS:
        raise ValueError("Choose supplier_delay, supplier_failure, or demand_spike.")
    scenario = SCENARIOS[scenario_key]
    hospital = connection.execute("SELECT * FROM hospitals WHERE id='ASTR'").fetchone()
    medicine = connection.execute("SELECT * FROM medicines WHERE id='NOREPI'").fetchone()
    stock = connection.execute(
        "SELECT * FROM inventory WHERE hospital_id='ASTR' AND medicine_id='NOREPI'"
    ).fetchone()
    supplier = connection.execute("SELECT * FROM suppliers WHERE id=?", (medicine["primary_supplier_id"],)).fetchone()
    effective_demand = float(stock["daily_demand"] or 0) * scenario["demand_multiplier"]
    stock_days = days_of_stock(stock["current_stock"], effective_demand)
    severity = "Critical" if stock_days is not None and stock_days <= 2 else "High"
    timestamp = now_iso()
    event_id = new_id("DSP")
    details = {
        "scenario": scenario_key,
        "supplier_id": supplier["id"],
        "supplier_name": supplier["name"],
        "supplier_status": "Delayed" if scenario_key == "supplier_delay" else ("Unavailable" if scenario_key == "supplier_failure" else supplier["status"]),
        "current_stock": float(stock["current_stock"]),
        "daily_demand": effective_demand,
        "baseline_daily_demand": float(stock["daily_demand"] or 0),
        "stock_days": stock_days,
        "eta_days": scenario["impact_days"],
        "uncertain": scenario["uncertain"],
        "simulated": True,
        "detected_at": timestamp,
    }
    connection.execute(
        """INSERT INTO disruptions
           (id,event_type,severity,title,summary,hospital_id,medicine_id,impact_days,status,details_json,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (event_id, scenario_key, severity, scenario["title"], scenario["summary"],
         hospital["id"], medicine["id"], scenario["impact_days"], "active",
         json.dumps(details), timestamp),
    )
    record_audit(
        connection, "agent.sensing", "Disruption Sensing Agent",
        "Detected " + scenario["title"] + " at " + hospital["name"] + ".",
        "disruption", event_id, details,
    )
    return {
        "id": event_id,
        "scenario": scenario_key,
        "title": scenario["title"],
        "summary": scenario["summary"],
        "severity": severity,
        "hospital_id": hospital["id"],
        "hospital_name": hospital["name"],
        "medicine_id": medicine["id"],
        "medicine_name": medicine["name"],
        "impact_days": scenario["impact_days"],
        "details": details,
        "created_at": timestamp,
    }
