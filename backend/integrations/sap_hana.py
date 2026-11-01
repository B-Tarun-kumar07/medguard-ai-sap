"""Optional SAP HANA Cloud sink for MedGuard shipment status events.

This is a sidecar event log; the demo's SQLite database remains the system of
record. Missing configuration or HANA errors never block shipment operations.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)

DEFAULT_HOST = "64e8c26b-3e07-47e9-b246-617058b0306e.hna3.prod-eu10.hanacloud.ondemand.com"


def configuration_status() -> dict:
    required = ("SAP_HANA_USER", "SAP_HANA_PASSWORD")
    missing = [key for key in required if not os.getenv(key)]
    status = {
        "provider": "SAP HANA Cloud",
        "configured": not missing,
        "missing_settings": missing,
        "host_configured": bool(os.getenv("SAP_HANA_HOST", DEFAULT_HOST)),
        "port": int(os.getenv("SAP_HANA_PORT", "443")),
        "event_type": "shipment.status.changed",
    }
    try:
        from backend import db
        with db.connect() as connection:
            counts = {row["status"]: row["total"] for row in connection.execute(
                "SELECT status,COUNT(*) AS total FROM hana_event_outbox GROUP BY status"
            ).fetchall()}
        status["outbox_pending"] = counts.get("pending", 0)
        status["outbox_sent"] = counts.get("sent", 0)
    except Exception:
        status["outbox_pending"] = 0
        status["outbox_sent"] = 0
    return status


def test_connection() -> dict:
    """Perform a read-only login check and return a user-safe diagnostic."""
    status = configuration_status()
    if not status["configured"]:
        return {"connected": False, "message": "Add the HANA database user and password in the backend environment first."}

    connection = None
    try:
        from hdbcli import dbapi

        connection = dbapi.connect(
            address=os.getenv("SAP_HANA_HOST", DEFAULT_HOST),
            port=int(os.getenv("SAP_HANA_PORT", "443")),
            user=os.environ["SAP_HANA_USER"],
            password=os.environ["SAP_HANA_PASSWORD"],
            encrypt=True,
            sslValidateCertificate=True,
            connectTimeout=10,
        )
        cursor = connection.cursor()
        cursor.execute("SELECT CURRENT_USER FROM DUMMY")
        cursor.fetchone()
        cursor.close()
        return {"connected": True, "message": "Connected to SAP HANA Cloud. The database login was accepted."}
    except ModuleNotFoundError:
        return {"connected": False, "message": "The HANA driver is missing. Run: python -m pip install -r backend\\requirements.txt"}
    except Exception as error:
        detail = str(error).lower()
        logger.warning("SAP HANA connection check failed: %s", error)
        if any(term in detail for term in ("timeout", "connect failed", "unreachable", "name or service")):
            message = "The HANA host could not be reached. The Hackfest network may block connections from this laptop."
        elif any(term in detail for term in ("authentication", "invalid user", "password", "authentication failed")):
            message = "HANA rejected the database login. Verify the group database user and rotated password."
        else:
            message = "HANA connection failed. Check the backend terminal for the diagnostic details."
        return {"connected": False, "message": message}
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def _deliver_event(event_id: str, event: dict) -> bool:
    status = configuration_status()
    if not status["configured"]:
        return False

    try:
        from hdbcli import dbapi

        connection = dbapi.connect(
            address=os.getenv("SAP_HANA_HOST", DEFAULT_HOST),
            port=int(os.getenv("SAP_HANA_PORT", "443")),
            user=os.environ["SAP_HANA_USER"],
            password=os.environ["SAP_HANA_PASSWORD"],
            encrypt=True,
            sslValidateCertificate=True,
            connectTimeout=10,
        )
        try:
            cursor = connection.cursor()
            cursor.execute(
                """CREATE COLUMN TABLE IF NOT EXISTS MEDGUARD_SHIPMENT_EVENTS (
                    EVENT_ID NVARCHAR(36) PRIMARY KEY,
                    SHIPMENT_ID NVARCHAR(128) NOT NULL,
                    SHIPMENT_STATUS NVARCHAR(40) NOT NULL,
                    OCCURRED_AT TIMESTAMP NOT NULL,
                    EVENT_JSON NCLOB NOT NULL
                )"""
            )
            occurred_at = datetime.now(timezone.utc)
            payload = {
                "eventType": "shipment.status.changed",
                "source": "MedGuard AI",
                "occurredAt": occurred_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "shipment": event,
            }
            cursor.execute(
                """UPSERT MEDGUARD_SHIPMENT_EVENTS
                   (EVENT_ID, SHIPMENT_ID, SHIPMENT_STATUS, OCCURRED_AT, EVENT_JSON)
                   VALUES (?, ?, ?, CURRENT_UTCTIMESTAMP, ?) WITH PRIMARY KEY""",
                (event_id, str(event.get("shipment_id", "unknown")), str(event.get("status", "unknown")), json.dumps(payload)),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()
        logger.info("Sent shipment status event to SAP HANA for shipment %s.", event.get("shipment_id"))
        return True
    except Exception as error:  # external adapter must not fail the local shipment flow
        logger.error("Could not send shipment event to SAP HANA: %s", error)
        return False


def _try_send_outbox_item(event_id: str, event: dict) -> bool:
    from backend import db

    sent = _deliver_event(event_id, event)
    with db.connect() as connection:
        if sent:
            connection.execute(
                "UPDATE hana_event_outbox SET status='sent',sent_at=?,last_error=NULL WHERE event_id=?",
                (db.now_iso(), event_id),
            )
        else:
            connection.execute(
                "UPDATE hana_event_outbox SET attempts=attempts+1,last_error=? WHERE event_id=?",
                ("HANA is not configured or could not be reached.", event_id),
            )
    return sent


def publish_shipment_status(event: dict) -> None:
    """Persist shipment events locally, then best-effort deliver them to HANA."""
    from backend import db

    event_id = str(event.get("event_id") or uuid4())
    with db.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO hana_event_outbox(event_id,event_json,status,created_at) VALUES(?,?, 'pending',?)",
            (event_id, json.dumps(event, ensure_ascii=False), db.now_iso()),
        )
    _try_send_outbox_item(event_id, event)


def outbox_status(limit: int = 20) -> dict:
    from backend import db

    with db.connect() as connection:
        counts = {row["status"]: row["total"] for row in connection.execute(
            "SELECT status,COUNT(*) AS total FROM hana_event_outbox GROUP BY status"
        ).fetchall()}
        events = connection.execute(
            "SELECT event_id,event_json,status,attempts,last_error,created_at,sent_at "
            "FROM hana_event_outbox ORDER BY created_at DESC LIMIT ?", (limit,),
        ).fetchall()
    return {
        "pending": counts.get("pending", 0), "sent": counts.get("sent", 0),
        "events": [{**dict(row), "event": json.loads(row["event_json"])} for row in events],
    }


def retry_pending_events() -> dict:
    from backend import db

    with db.connect() as connection:
        rows = connection.execute(
            "SELECT event_id,event_json FROM hana_event_outbox WHERE status='pending' ORDER BY created_at"
        ).fetchall()
    sent = sum(1 for row in rows if _try_send_outbox_item(row["event_id"], json.loads(row["event_json"])))
    result = outbox_status()
    result["retried"] = len(rows)
    result["sent_now"] = sent
    return result
