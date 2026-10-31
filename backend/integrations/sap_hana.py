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
    return {
        "provider": "SAP HANA Cloud",
        "configured": not missing,
        "missing_settings": missing,
        "host_configured": bool(os.getenv("SAP_HANA_HOST", DEFAULT_HOST)),
        "port": int(os.getenv("SAP_HANA_PORT", "443")),
        "event_type": "shipment.status.changed",
    }


def publish_shipment_status(event: dict) -> None:
    """Append an event to MEDGUARD_SHIPMENT_EVENTS in the configured HANA schema."""
    status = configuration_status()
    if not status["configured"]:
        logger.info("SAP HANA is not configured; shipment event was not sent.")
        return

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
                """INSERT INTO MEDGUARD_SHIPMENT_EVENTS
                   (EVENT_ID, SHIPMENT_ID, SHIPMENT_STATUS, OCCURRED_AT, EVENT_JSON)
                   VALUES (?, ?, ?, CURRENT_UTCTIMESTAMP, ?)""",
                (str(uuid4()), str(event.get("shipment_id", "unknown")), str(event.get("status", "unknown")), json.dumps(payload)),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()
        logger.info("Sent shipment status event to SAP HANA for shipment %s.", event.get("shipment_id"))
    except Exception as error:  # external adapter must not fail the local shipment flow
        logger.error("Could not send shipment event to SAP HANA: %s", error)
