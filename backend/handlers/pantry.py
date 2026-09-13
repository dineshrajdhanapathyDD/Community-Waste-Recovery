"""
Pantry tool — current stock levels at partner pantries.

Matches schemas/get-pantry-levels-api.json: GET /pantry with an optional
resource_id filter. Adds a computed `is_low` flag (quantity_on_hand <=
low_stock_threshold) so the agent can spot shortages, while keeping every
field the schema declares.

MIT License - Copyright (c) 2026 Dineshraj Dhanapathy@DD
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, json_response, get_params  # noqa: E402


def handler(event, context=None):
    params = get_params(event)
    resource_id = params.get("resource_id")

    items = load("pantry_levels")
    if resource_id:
        items = [i for i in items if i["resource_id"] == resource_id]

    # Add a computed low-stock flag (extra, schema-compatible field).
    enriched = []
    for item in items:
        row = dict(item)
        row["is_low"] = item["quantity_on_hand"] <= item["low_stock_threshold"]
        enriched.append(row)

    return json_response(200, {
        "pantry_items": enriched,
        "count": len(enriched),
    })
