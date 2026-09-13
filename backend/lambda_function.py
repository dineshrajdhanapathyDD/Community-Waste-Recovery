"""
AWS Lambda entrypoint for the Good Neighbor backend.

One Lambda serves every tool, routed by path — the cloud equivalent of
server.py. It's fronted by an HTTP API Gateway (payload format 2.0) defined in
template.yaml. The existing handlers are reused unchanged; this module only
adapts the API Gateway event shape and dispatches by path.

MIT License - Copyright (c) 2026 Dineshraj Dhanapathy@DD
"""
import json

from handlers import community, pantry, logistics, guidelines


def _event_path(event):
    """Path for both HTTP API (v2) and REST API (v1) proxy events."""
    rc = event.get("requestContext", {})
    if "http" in rc:  # HTTP API payload format 2.0
        return rc["http"].get("path", "/")
    return event.get("path", "/")  # REST API / fallback


def _normalize(event):
    """Ensure queryStringParameters / pathParameters / body exist."""
    event.setdefault("queryStringParameters", None)
    event["queryStringParameters"] = event.get("queryStringParameters") or {}
    event.setdefault("pathParameters", None)
    event["pathParameters"] = event.get("pathParameters") or {}
    return event


def handler(event, context=None):
    event = _normalize(event)
    path = (_event_path(event) or "/").rstrip("/") or "/"

    # Community gateway root == surplus listings (matches the schema's "GET /").
    if path in ("/", "/surplus"):
        return community.surplus_listings_handler(event)
    if path == "/catalog":
        return community.resource_catalog_handler(event)
    if path == "/needs":
        return community.recipient_needs_handler(event)
    if path == "/pantry":
        return pantry.handler(event)

    if path == "/volunteers":
        return logistics.volunteers_handler(event)
    if path.startswith("/volunteers/"):
        event["pathParameters"]["volunteer_id"] = path.split("/", 2)[2]
        return logistics.volunteers_handler(event)

    if path == "/vehicles":
        return logistics.vehicles_handler(event)
    if path.startswith("/vehicles/"):
        event["pathParameters"]["vehicle_id"] = path.split("/", 2)[2]
        return logistics.vehicles_handler(event)

    if path == "/guidelines":
        return guidelines.handler(event)

    if path == "/health":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"status": "ok"}),
        }

    return {
        "statusCode": 404,
        "headers": {"Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"},
        "body": json.dumps({"error": f"No route for {path}"}),
    }
