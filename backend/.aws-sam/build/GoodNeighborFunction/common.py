"""
Shared helpers for the Good Neighbor backend tools.

Each tool (guidelines, surplus, catalog, needs, pantry, volunteers, vehicles) is
a small Lambda-style handler that reads seed JSON from backend/data/ and returns
a response matching the OpenAPI / Lambda schema in ../schemas.

The same handlers run three ways:
  * as AWS Lambda functions (behind API Gateway / an AgentCore Gateway target),
  * behind the local dev server (server.py) for no-AWS testing,
  * imported directly in unit tests.

MIT License - Copyright (c) 2026 Dineshraj Dhanapathy@DD
"""
import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Cache loaded files so repeated tool calls in one process don't re-read disk.
_CACHE = {}


def load(name):
    """Load and cache backend/data/<name>.json."""
    if name not in _CACHE:
        path = os.path.join(DATA_DIR, f"{name}.json")
        with open(path, "r", encoding="utf-8") as fh:
            _CACHE[name] = json.load(fh)
    return _CACHE[name]


def json_response(status_code, body):
    """Shape an API-Gateway-style proxy response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            # CORS so the frontend/local tools can call these directly.
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(body),
    }


def error(status_code, message):
    return json_response(status_code, {"error": message})


def get_params(event):
    """Pull query-string params from a Lambda proxy event (or {} locally)."""
    return (event or {}).get("queryStringParameters") or {}


def get_path_params(event):
    return (event or {}).get("pathParameters") or {}


# ---------------------------------------------------------------------------
# Date helpers for the volunteer / vehicle "dd-Month-yyyy" format.
# ---------------------------------------------------------------------------
_DATE_FMT = "%d-%B-%Y"


def parse_date(value):
    """Parse a 'dd-Month-yyyy' string into a datetime, or None if it can't."""
    try:
        return datetime.strptime(value, _DATE_FMT)
    except (ValueError, TypeError):
        return None


def format_date(dt):
    """Format a datetime back to 'dd-Month-yyyy' (no leading-zero portability issues)."""
    return f"{dt.day:02d}-{dt.strftime('%B')}-{dt.year}"


def days_since(value, now=None):
    """Whole days between a 'dd-Month-yyyy' date and now (None if unparseable)."""
    dt = parse_date(value)
    if dt is None:
        return None
    now = now or datetime.utcnow()
    return (now - dt).days


def years_between(value, now=None):
    """Years (1 decimal) between a 'dd-Month-yyyy' date and now."""
    d = days_since(value, now)
    if d is None:
        return None
    return round(d / 365.25, 1)
