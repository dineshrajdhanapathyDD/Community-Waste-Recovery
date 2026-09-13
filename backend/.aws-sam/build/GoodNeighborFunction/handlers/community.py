"""
Community tool group — three handlers behind the community gateway:

  * surplus_listings  -> GET /            (schemas/view-surplus-listings-api.json)
  * resource_catalog  -> GET /            (schemas/view-resource-catalog-api.json)
  * recipient_needs   -> GET /needs       (schemas/get-recipient-needs-api.json)

Each returns a response matching its schema. Filtering is done in-process over
the seed data.

MIT License - Copyright (c) 2026 Dineshraj Dhanapathy@DD
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, json_response, get_params  # noqa: E402


# ---------------------------------------------------------------------------
# Surplus listings
# ---------------------------------------------------------------------------
def surplus_listings_handler(event, context=None):
    """Return surplus donation listings.

    The schema exposes org_role / org_area on the response. In a real deployment
    those come from the caller's identity; here we report the Coordinator view
    (all areas) so the agent sees the full network.
    """
    listings = load("surplus_listings")
    return json_response(200, {
        "listings": listings,
        "count": len(listings),
        "org_role": "Coordinator",
        "org_area": "Citywide",
    })


# ---------------------------------------------------------------------------
# Resource catalog
# ---------------------------------------------------------------------------
def resource_catalog_handler(event, context=None):
    """Return the community resource catalog, optionally filtered.

    Query params (both optional):
      category  exact category match (case-insensitive)
      resource  contains-search on the resource name (case-insensitive)
    """
    params = get_params(event)
    category = params.get("category")
    resource = params.get("resource")

    resources = load("resources")
    filtered = resources

    if category:
        filtered = [r for r in filtered if r["category"].lower() == category.lower()]
    if resource:
        needle = resource.lower()
        filtered = [r for r in filtered if needle in r["resource"].lower()]

    return json_response(200, {
        "resources": filtered,
        "count": len(filtered),
        "filters_applied": {
            "category": category,
            "resource": resource,
        },
    })


# ---------------------------------------------------------------------------
# Recipient needs
# ---------------------------------------------------------------------------
def recipient_needs_handler(event, context=None):
    """Return recipient needs, optionally filtered by resource_id or org_id."""
    params = get_params(event)
    resource_id = params.get("resource_id")
    org_id = params.get("org_id")

    needs = load("recipient_needs")
    filtered = needs

    if resource_id:
        filtered = [n for n in filtered if n["resource_id"] == resource_id]
    if org_id:
        filtered = [n for n in filtered if n["org_id"] == org_id]

    return json_response(200, {
        "needs": filtered,
        "count": len(filtered),
    })
