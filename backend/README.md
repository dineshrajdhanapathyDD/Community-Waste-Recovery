# Good Neighbor Agent — Backend Tools & Data

This is the **backend** the agent talks to: the actual tool implementations plus
real seed data behind the seven contracts in [`../schemas`](../schemas). Each
tool reads JSON from `data/` and returns a response that matches its schema.

The same handlers run three ways with no code changes:

- **Locally** via `server.py` — one process, no AWS, for development and demos.
- **As AWS Lambda functions** behind API Gateway / an AgentCore Gateway target.
- **Imported directly** in tests.

## Folder structure

```
backend/
├── README.md              # This file
├── server.py              # Local dev server (stdlib only) — runs every tool
├── lambda_function.py     # AWS Lambda entrypoint (routes by path, reuses handlers)
├── template.yaml          # AWS SAM template (Lambda + HTTP API Gateway)
├── samconfig.toml         # SAM deploy defaults (stack name, region)
├── common.py              # Shared: data loading, responses, date helpers
├── data/                  # The "real" seed data (source of truth)
│   ├── resources.json         # Catalog (RES### — referenced by everything)
│   ├── organizations.json     # Orgs (ORG### — donor / recipient / coordinator)
│   ├── surplus_listings.json  # Donor-posted surplus (LIST### → RES### items)
│   ├── recipient_needs.json   # What recipients request (NEED### → ORG###/RES###)
│   ├── pantry_levels.json     # Partner stock (→ ORG###/RES###, low-stock aware)
│   ├── volunteers.json        # Drivers (VOL###)
│   ├── vehicles.json          # Vehicles (VEH###)
│   └── guidelines.json        # Acceptance / Window / Handling text
└── handlers/              # One module per tool group (mirrors agent.py groups)
    ├── guidelines.py          # get-guidelines  (Lambda schema)
    ├── community.py           # surplus + catalog + needs
    ├── pantry.py              # pantry levels
    └── logistics.py           # volunteers + vehicles
```

## Data model

The data is cross-referenced so the agent can actually reason about it — match
surplus to a need, then find a driver:

```
resources (RES###) ──referenced by──▶ surplus items, needs, pantry
organizations (ORG###) ──────────────▶ needs, pantry (owner org)
surplus_listings (LIST###) ── items ─▶ resources
recipient_needs (NEED###) ───────────▶ org + resource + priority
pantry_levels ───────────────────────▶ org + resource + on-hand vs threshold
volunteers (VOL###) / vehicles (VEH###) ─ location + availability/capacity
```

Example the data supports end to end:

> Riverside Grocery posted **40 lbs of produce** (`LIST12AB34CD`, pickup by
> 2026-09-12). North Side Food Bank needs **50 lbs of fresh tomatoes**
> (`NEED001`, high priority) and is **low on tomatoes** (8 on hand, threshold
> 20). Volunteer **Maria Alvarez** (`VOL001`, North Side, available) with the
> **refrigerated van** `VEH001` can move it.

Dates are set relative to the project's "today" (September 2026), so pickup
windows and volunteer tenure compute to sensible values.

## Endpoints (local dev server)

Start it, then call any route. All return JSON matching the schemas.

| Route | Tool | Query params |
|-------|------|--------------|
| `GET /` | Surplus listings | — |
| `GET /catalog` | Resource catalog | `category`, `resource` (contains) |
| `GET /needs` | Recipient needs | `resource_id`, `org_id` |
| `GET /pantry` | Pantry levels | `resource_id` |
| `GET /volunteers` | Volunteers | `volunteer_id`, `location`, `firstname`, `lastname`, `available`, `limit` |
| `GET /volunteers/{id}` | One volunteer | — |
| `GET /vehicles` | Vehicles | `vehicle_id`, `location`, `capacity`, `type`, `limit` |
| `GET /vehicles/{id}` | One vehicle | — |
| `GET\|POST /guidelines` | Guidelines | `guideline_type` = `Acceptance` \| `Window` \| `Handling` (or JSON body) |
| `GET /health` | Health check | — |

> Surplus and catalog each map to `GET /` in their **individual** schemas (they
> are separate API Gateways in AWS). In the single local server they'd collide,
> so the catalog is served at `/catalog` while surplus keeps the root `/`.

### Computed fields

Some responses add fields the schemas define as computed (not stored in
`data/`):

- **Volunteers:** `full_name`, `years_of_service` (from `joined_date`).
- **Vehicles:** `days_since_check`, `maintenance_status`
  (`current` < 150d, `due_soon` < 180d, else `overdue`), `next_check_due`
  (last check + 180 days).
- **Pantry:** `is_low` (`quantity_on_hand <= low_stock_threshold`).

## Run it locally (no AWS)

Requires only Python 3.8+ (standard library — nothing to install).

```bash
# from the repo root
python backend/server.py                 # http://localhost:8080
# or a custom port
PORT=9000 python backend/server.py       # bash
$env:PORT=9000; python backend/server.py # PowerShell
```

Then:

```bash
curl http://localhost:8080/pantry
curl "http://localhost:8080/catalog?category=produce"
curl "http://localhost:8080/needs?resource_id=RES001"
curl "http://localhost:8080/volunteers?available=true"
curl "http://localhost:8080/vehicles?capacity=van"
curl "http://localhost:8080/guidelines?guideline_type=Window"
```

CORS is enabled on every route, so a browser frontend can call the local server
directly during development.

## Editing the data

`data/*.json` is the source of truth — edit those files to change what the agent
sees. Keep the ID references consistent:

- A `surplus_listings[].items[].resource_id` should exist in `resources.json`.
- `recipient_needs[].org_id` / `pantry_levels[].org_id` should exist in
  `organizations.json`; their `resource_id` in `resources.json`.
- Volunteer/vehicle dates use the `dd-Month-yyyy` format (e.g. `15-March-2022`).

The dev server caches files per process, so restart it after editing data.

## Deploying to AWS (Lambda + HTTP API Gateway via SAM)

The backend ships with an AWS SAM template that deploys **one Lambda**
(`lambda_function.py`, which routes by path just like `server.py`) behind an
**HTTP API Gateway**, with the `data/` seed bundled into the function.

Prerequisites: AWS CLI configured, AWS SAM CLI, and Python 3.12.

```bash
cd backend
sam build
sam deploy            # uses samconfig.toml (stack: good-neighbor-backend, us-east-1)
```

`sam deploy` prints the live base URL as the `ApiBaseUrl` output. Test it:

```bash
BASE=https://<api-id>.execute-api.us-east-1.amazonaws.com
curl "$BASE/pantry"
curl "$BASE/needs?resource_id=RES001"
curl "$BASE/guidelines?guideline_type=Window"
```

> **Note on the SAM CLI exit code on Windows/PowerShell:** `sam build`/`sam
> deploy` may report a non-zero exit code because their progress banner is
> written to stderr. Trust the textual result (`Build Succeeded` /
> `Successfully created/updated stack`), not the shell exit code.

### Update / redeploy

Edit code or `data/*.json`, then:

```bash
sam build && sam deploy
```

### Tear it down (removes everything)

```bash
sam delete --stack-name good-neighbor-backend --region us-east-1
```

This deletes the Lambda, the HTTP API, the IAM role, and the CloudFormation
stack. (The SAM-managed artifact S3 bucket is shared across SAM projects and is
left in place.)

### Auth note

The deployed HTTP API is **open (no auth)** so it's directly testable, mirroring
the local server. In the full architecture, the **AgentCore Gateway** layer adds
inbound auth (SigV4 for guidelines, OAuth2 for the others) when you register
these endpoints as gateway targets using the schema files in
[`../schemas`](../schemas), then set the agent's `*_GATEWAY_URL` env vars (see
the root [`README.md`](../README.md#configuration)). Add an API Gateway
authorizer to `template.yaml` if you want auth at the API layer too.

### Toward production data

For a production build you'd typically move `data/` into DynamoDB (the
volunteer/vehicle schemas already reference `LocationIndex` / `CapacityIndex`
GSIs). All data access is isolated in `common.load()`, so swapping the JSON
loader for a DynamoDB client is a localized change.

## License

MIT — see [`../LICENSE`](../LICENSE).
