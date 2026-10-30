"""Sequential coordinator for the five specialized demo agents."""

from __future__ import annotations

import sqlite3

from backend.db import get_settings, record_audit
from backend.agents.sensing import detect
from backend.agents.scenario import analyze
from backend.agents.inventory import plan_allocations
from backend.agents.logistics import enrich_recommendations
from backend.agents.compliance import queue_approvals


def run_disruption_workflow(connection: sqlite3.Connection, scenario_key: str) -> dict:
    settings = get_settings(connection)
    disruption = detect(connection, scenario_key)
    planning = analyze(
        connection, disruption,
        int(settings.get("critical_days", 3)),
        int(settings.get("warning_days", 7)),
    )
    allocation = plan_allocations(connection, disruption, planning)
    allocation = enrich_recommendations(connection, allocation)
    approvals = queue_approvals(connection, allocation["recommendations"])
    result = {
        "disruption": disruption,
        "planning": planning,
        "inventory": allocation,
        "approvals": approvals,
        "agent_steps": [
            {"agent":"Disruption Sensing Agent","status":"Complete","summary":"Flagged " + disruption["severity"].lower() + " risk from the simulated supplier or demand signal."},
            {"agent":"Scenario Planning Agent","status":"Complete","summary":str(planning["affected_hospitals"]) + " hospital(s) are projected to run short within the event horizon."},
            {"agent":"Inventory and Allocation Agent","status":"Complete","summary":str(len(allocation["recommendations"])) + " safety-checked stock transfer proposal(s); " + str(len(allocation["supplier_options"])) + " alternative supplier(s) found."},
            {"agent":"Logistics and Transportation Agent","status":"Complete","summary":"Compared feasible simulated routes and shipment capacities."},
            {"agent":"Compliance and Human-in-the-Loop Agent","status":"Awaiting review" if approvals else "Complete","summary":str(len(approvals)) + " action(s) queued; no critical action was auto-executed."},
        ],
    }
    record_audit(
        connection, "workflow.completed", "MedGuard coordinator",
        "Multi-agent response planning finished and hand-offs were recorded.",
        "disruption", disruption["id"],
        {"agent_steps": result["agent_steps"], "human_approval_required": True},
    )
    return result
