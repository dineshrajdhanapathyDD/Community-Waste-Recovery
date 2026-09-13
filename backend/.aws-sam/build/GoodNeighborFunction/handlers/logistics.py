"""
Logistics tool group — volunteers and vehicles for pickups/deliveries.

  * volunteers -> GET /volunteers, GET /volunteers/{id}  (schemas/get-volunteer-api.json)
  * vehicles   -> GET /vehicles,   GET /vehicles/{id}    (schemas/get-vehicle-api.json)

Both add the schema's computed fields:
  volunteers: full_name, years_of_service
  vehicles:   days_since_check, maintenance_status, next_check_due
and both return the summary blocks the schemas declare.

MIT License - Copyright (c) 2026 Dineshraj Dhanapathy@DD
"""
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import (  # noqa: E402
    load, json_response, error, get_params, get_path_params,
    parse_date, format_date, days_since, years_between,
)

# A safety check is "current" under this many days, "due_soon" up to the overdue
# line, and "overdue" beyond it. Next check is due 180 days after the last one.
_DUE_SOON_DAYS = 150
_OVERDUE_DAYS = 180


def _truthy(value):
    return str(value).lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Volunteers
# ---------------------------------------------------------------------------
def _enrich_volunteer(v):
    row = dict(v)
    row["full_name"] = f"{v['firstname']} {v['lastname']}"
    yrs = years_between(v["joined_date"])
    if yrs is not None:
        row["years_of_service"] = yrs
    return row


def volunteers_handler(event, context=None):
    # Single volunteer by path id: /volunteers/{volunteer_id}
    path = get_path_params(event)
    if path.get("volunteer_id"):
        vid = path["volunteer_id"]
        for v in load("volunteers"):
            if v["volunteer_id"] == vid:
                return json_response(200, _enrich_volunteer(v))
        return error(404, f"Volunteer '{vid}' not found")

    params = get_params(event)
    vols = load("volunteers")

    if params.get("volunteer_id"):
        vols = [v for v in vols if v["volunteer_id"] == params["volunteer_id"]]
    if params.get("location"):
        needle = params["location"].lower()
        vols = [v for v in vols if needle in v["location"].lower()]
    if params.get("firstname"):
        needle = params["firstname"].lower()
        vols = [v for v in vols if needle in v["firstname"].lower()]
    if params.get("lastname"):
        needle = params["lastname"].lower()
        vols = [v for v in vols if needle in v["lastname"].lower()]
    if params.get("available") is not None and params.get("available") != "":
        want = _truthy(params["available"])
        vols = [v for v in vols if v.get("available", False) == want]

    limit = int(params.get("limit", 50) or 50)
    vols = vols[:limit]
    enriched = [_enrich_volunteer(v) for v in vols]

    locations_summary = {}
    for v in enriched:
        locations_summary[v["location"]] = locations_summary.get(v["location"], 0) + 1

    return json_response(200, {
        "volunteers": enriched,
        "count": len(enriched),
        "filters_applied": {
            k: params.get(k)
            for k in ("volunteer_id", "location", "firstname", "lastname", "available")
            if params.get(k) is not None
        },
        "locations_summary": locations_summary,
    })


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------
def _enrich_vehicle(v):
    row = dict(v)
    d = days_since(v["last_safety_check"])
    if d is not None:
        row["days_since_check"] = d
        if d < _DUE_SOON_DAYS:
            status = "current"
        elif d < _OVERDUE_DAYS:
            status = "due_soon"
        else:
            status = "overdue"
        row["maintenance_status"] = status
        last = parse_date(v["last_safety_check"])
        if last is not None:
            row["next_check_due"] = format_date(last + timedelta(days=_OVERDUE_DAYS))
    return row


def vehicles_handler(event, context=None):
    # Single vehicle by path id: /vehicles/{vehicle_id}
    path = get_path_params(event)
    if path.get("vehicle_id"):
        vid = path["vehicle_id"]
        for v in load("vehicles"):
            if v["vehicle_id"] == vid:
                return json_response(200, _enrich_vehicle(v))
        return error(404, f"Vehicle '{vid}' not found")

    params = get_params(event)
    vehicles = load("vehicles")

    if params.get("vehicle_id"):
        vehicles = [v for v in vehicles if v["vehicle_id"] == params["vehicle_id"]]
    if params.get("location"):
        needle = params["location"].lower()
        vehicles = [v for v in vehicles if needle in v["location"].lower()]
    if params.get("capacity"):
        vehicles = [v for v in vehicles if v["capacity"] == params["capacity"]]
    if params.get("type"):
        needle = params["type"].lower()
        vehicles = [v for v in vehicles if needle in v["type"].lower()]

    limit = int(params.get("limit", 50) or 50)
    vehicles = vehicles[:limit]
    enriched = [_enrich_vehicle(v) for v in vehicles]

    by_location, by_capacity, by_type = {}, {}, {}
    maintenance_due_count = 0
    for v in enriched:
        by_location[v["location"]] = by_location.get(v["location"], 0) + 1
        by_capacity[v["capacity"]] = by_capacity.get(v["capacity"], 0) + 1
        by_type[v["type"]] = by_type.get(v["type"], 0) + 1
        if v.get("maintenance_status") in ("due_soon", "overdue"):
            maintenance_due_count += 1

    if not enriched:
        return error(404, "No vehicles found matching the criteria")

    return json_response(200, {
        "vehicles": enriched,
        "count": len(enriched),
        "filters_applied": {
            k: params.get(k)
            for k in ("vehicle_id", "location", "capacity", "type")
            if params.get(k) is not None
        },
        "summary": {
            "by_location": by_location,
            "by_capacity": by_capacity,
            "by_type": by_type,
            "maintenance_due_count": maintenance_due_count,
        },
    })
