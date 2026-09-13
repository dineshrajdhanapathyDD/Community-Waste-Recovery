"""
Guidelines tool — donation & food-safety guidelines.

Matches schemas/get-guidelines-lambda.json: takes {"guideline_type": "..."} where
type is one of Acceptance | Window | Handling, and returns
{"guideline_details": "..."}.

This is the Lambda-target tool (SigV4 inbound auth in the agent). Because it's a
Lambda schema (not an OpenAPI/API-Gateway target), its handler reads the input
directly from the event rather than from query-string parameters.

MIT License - Copyright (c) 2026 Dineshraj Dhanapathy@DD
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, json_response, error  # noqa: E402

VALID_TYPES = ("Acceptance", "Window", "Handling")


def _extract_type(event):
    """Guideline Lambda targets can receive input a few ways; support them all."""
    if not event:
        return None
    # AgentCore/Lambda direct invoke: the input object itself.
    if "guideline_type" in event:
        return event["guideline_type"]
    # Wrapped under a body (API-Gateway-proxy style).
    body = event.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (ValueError, TypeError):
            body = {}
    if isinstance(body, dict) and "guideline_type" in body:
        return body["guideline_type"]
    # Query string fallback (handy for the local dev server / curl).
    qs = event.get("queryStringParameters") or {}
    return qs.get("guideline_type")


def handler(event, context=None):
    guideline_type = _extract_type(event)

    if not guideline_type:
        return error(400, "guideline_type is required (Acceptance, Window, or Handling)")
    if guideline_type not in VALID_TYPES:
        return error(
            400,
            f"Invalid guideline_type '{guideline_type}'. Must be one of: {', '.join(VALID_TYPES)}",
        )

    guidelines = load("guidelines")
    details = guidelines.get(guideline_type)
    if not details:
        return error(404, f"No guideline found for '{guideline_type}'")

    return json_response(200, {"guideline_details": details})
