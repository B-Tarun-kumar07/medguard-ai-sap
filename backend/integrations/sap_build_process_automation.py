"""Optional SAP Build Process Automation workflow trigger for medicine requests.

The local request remains the source of truth. If BPA is configured, MedGuard
starts a separate SAP workflow after saving the request; integration failures
are logged and never undo the local request.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

CONFIG_KEYS = (
    "SAP_BPA_API_URL",
    "SAP_BPA_TOKEN_URL",
    "SAP_BPA_CLIENT_ID",
    "SAP_BPA_CLIENT_SECRET",
    "SAP_BPA_WORKFLOW_DEFINITION_ID",
)


def configuration_status() -> dict:
    missing = [key for key in CONFIG_KEYS if not os.getenv(key)]
    return {
        "provider": "SAP Build Process Automation",
        "configured": not missing,
        "missing_settings": missing,
        "event_type": "medicine.request.created",
    }


def _access_token() -> str:
    client_id = os.environ["SAP_BPA_CLIENT_ID"]
    client_secret = os.environ["SAP_BPA_CLIENT_SECRET"]
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    request = Request(
        os.environ["SAP_BPA_TOKEN_URL"],
        data=urlencode({"grant_type": "client_credentials"}).encode("ascii"),
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=8) as response:
        result = json.loads(response.read().decode("utf-8"))
    token = result.get("access_token")
    if not token:
        raise ValueError("SAP OAuth response did not contain an access token.")
    return token


def start_medicine_request_workflow(context: dict) -> None:
    """Start a configured BPA workflow without affecting the local request."""
    if not configuration_status()["configured"]:
        return

    api_url = os.environ["SAP_BPA_API_URL"].rstrip("/")
    if not api_url.endswith("/workflow/rest/v1/workflow-instances"):
        api_url += "/workflow/rest/v1/workflow-instances"
    payload = {"definitionId": os.environ["SAP_BPA_WORKFLOW_DEFINITION_ID"], "context": context}
    try:
        request = Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {_access_token()}", "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=8) as response:
            if response.status >= 300:
                raise RuntimeError(f"SAP Build Process Automation returned HTTP {response.status}.")
        logger.info("Started SAP Build Process Automation workflow for medicine request %s.", context.get("requestId"))
    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, OSError) as error:
        logger.error("Could not start SAP Build Process Automation workflow for medicine request %s: %s", context.get("requestId"), error)
