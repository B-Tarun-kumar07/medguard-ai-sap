"""Human approval gate. No purchase or stock movement is created before approval."""

from __future__ import annotations

import sqlite3

from backend.db import new_id, now_iso, record_audit


def queue_approvals(connection: sqlite3.Connection, recommendations: list[dict]) -> list[dict]:
    queued = []
    for recommendation in recommendations:
        approval_id = new_id("APR")
        connection.execute(
            """INSERT INTO approvals(id,recommendation_id,decision,reviewer,reason,created_at)
               VALUES (?,?, 'pending',NULL,NULL,?)""",
            (approval_id, recommendation["id"], now_iso()),
        )
        queued.append({**recommendation, "approval_id": approval_id, "decision": "pending"})
    record_audit(
        connection, "agent.compliance", "Compliance and Human-in-the-Loop Agent",
        f"Queued {len(queued)} critical action(s) for authorized human review; none were executed automatically.",
        "approval_batch", queued[0]["approval_id"] if queued else None,
        {"approval_ids": [item["approval_id"] for item in queued], "automatic_execution": False},
    )
    return queued


def latest_decision(connection: sqlite3.Connection, recommendation_id: str) -> dict | None:
    row = connection.execute(
        "SELECT * FROM approvals WHERE recommendation_id=? ORDER BY created_at DESC LIMIT 1",
        (recommendation_id,),
    ).fetchone()
    return dict(row) if row else None
