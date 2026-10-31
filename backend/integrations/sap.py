"""Optional SAP Integration Suite event adapter.

When configured, shipment status changes are posted to a deployed Integration
Suite iFlow using OAuth 2.0 client credentials. Missing configuration leaves
the local demo fully operational and does not send any data externally.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

CONFIG_KEYS = (
    "SAP_INTEGRATION_SUITE_SHIPMENT_URL",
    "SAP_OAUTH_TOKEN_URL",
    "SAP_OAUTH_CLIENT_ID",
    "SAP_OAUTH_CLIENT_SECRET",
)


def configuration_status() -> dict:
    missing = [key for key in CONFIG_KEYS if not os.getenv(key)]
    return {
        "provider": "SAP Integration Suite",
        "configured": not missing,
        "missing_settings": missing,
        "event_type": "shipment.status.changed",
    }


def _access_token() -> str:
    token_url = os.environ["SAP_OAUTH_TOKEN_URL"]
    client_id = os.environ["SAP_OAUTH_CLIENT_ID"]
    client_secret = os.environ["SAP_OAUTH_CLIENT_SECRET"]
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    request = Request(
        token_url,
        data=urlencode({"grant_type": "client_credentials"}).encode("ascii"),
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        result = json.loads(response.read().decode("utf-8"))
    token = result.get("access_token")
    if not token:
        raise ValueError("SAP OAuth response did not contain an access token.")
    return token


def publish_shipment_status(event: dict) -> None:
    """Send a shipment status event to SAP; never fail the local shipment flow."""
    if not configuration_status()["configured"]:
        logger.info("SAP Integration Suite is not configured; shipment event was not sent.")
        return

    payload = {
        "eventType": "shipment.status.changed",
        "source": "MedGuard AI",
        "occurredAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "shipment": event,
    }
    try:
        request = Request(
            os.environ["SAP_INTEGRATION_SUITE_SHIPMENT_URL"],
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {_access_token()}", "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=15) as response:
            if response.status >= 300:
                raise RuntimeError(f"SAP Integration Suite returned HTTP {response.status}.")
        logger.info("Sent shipment status event to SAP Integration Suite for shipment %s.", event.get("shipment_id"))
    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, OSError) as error:
        logger.error("Could not send shipment event to SAP Integration Suite: %s", error)
