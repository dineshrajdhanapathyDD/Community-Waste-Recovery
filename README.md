# Good Neighbor Agent — Community Waste Recovery

An AI assistant that helps a whole **community** recover and redistribute
surplus instead of throwing it away. It serves **groups of people** —
neighborhoods, nonprofits, food banks, shelters, schools, libraries, and small
local organizations — by connecting people who have surplus (grocers,
restaurants, schools) with people who can use it (food banks, shelters,
neighbors), and by routing volunteers to move it.

The agent is a [Strands](https://strandsagents.com/) agent running on the
**Amazon Bedrock AgentCore Runtime**. It reaches every backend tool through
**AgentCore Gateway** (MCP endpoints), authenticates with **Amazon Cognito**,
mints outbound tokens via **AgentCore Identity**, and can filter which tools
each organization sees with **Amazon Verified Permissions (AVP)**.

## Quick start — what to run

Pick the level you want. Each step builds on the previous one, but you can stop
at any level and still have something working.

### Level 0 — See the UI, no AWS, nothing installed but Python

```bash
cd static
python -m http.server 8000
# open http://localhost:8000, sign in with any email + code 123456
```

The app runs in **Demo mode** (mocked replies) — good for seeing the animated
frontend and the "How it works" panel.

### Level 1 — Run the real backend locally (still no AWS)

In a **first** terminal, start the backend tools API:

```bash
python backend/server.py            # http://localhost:8080
```

Point the frontend at it by setting `BACKEND_API_URL` in `static/config.js`:

```js
BACKEND_API_URL: 'http://localhost:8080',
```

Then in a **second** terminal serve the frontend (as in Level 0). Sign in with
any email + `123456` and ask "which volunteers are available?" — answers now
come from the real backend handlers + seed data. Badge shows **Live backend
data**.

### Level 2 — Deploy the backend to AWS (Lambda + API Gateway)

Requires the AWS CLI + AWS SAM CLI configured with credentials.

```bash
cd backend
sam build
sam deploy                          # stack: good-neighbor-backend (us-east-1)
```

Copy the `ApiBaseUrl` from the output into `static/config.js` as
`BACKEND_API_URL`. The frontend now talks to your live AWS backend.
Tear it down later with:

```bash
sam delete --stack-name good-neighbor-backend --region us-east-1
```

### Level 3 — Deploy the frontend to AWS Amplify Hosting

Push this repo to your Git provider, then in the **Amplify console**:
*New app → Host web app → connect the repo → deploy*. Amplify auto-detects
[`amplify.yml`](amplify.yml) and publishes `static/` over HTTPS + CDN.

### Level 4 — Deploy the full agent (Claude via AgentCore)

Requires the **`bootstrap-stack`** and the **AgentCore CLI** (see
[Prerequisites](#prerequisites)).

```bash
cd static/AgentCode
./launchAgent.sh                    # deploys the runtime + publishes the frontend
```

This is the complete architecture: browser → Cognito → AgentCore Runtime →
Claude → Gateway (MCP) → your backend tools. See
[Deploying the agent](#deploying-the-agent) for details.

> New here? Do **Level 0** first (10 seconds), then **Level 1** to see real
> data. Levels 2–4 add AWS one piece at a time.

## What it can do

- **Donation & food-safety guidelines** — acceptance rules and safe donation
  windows for prepared food, produce, and packaged goods.
- **Surplus donation listings** — surplus food and goods posted by donors.
- **Community resource catalog** — the categories of items circulating in the
  network.
- **Recipient needs** — what food banks, shelters, and partners are requesting,
  so surplus can be matched to real demand.
- **Pantry / stock levels** — current stock at partner pantries, to spot
  shortages and prioritize where surplus should go.
- **Volunteers & vehicles** — available drivers and vehicles (location and
  capacity) for planning pickups and deliveries.

Example questions the agent can answer (only from live tool data):

> "A grocer has 40 lbs of produce that must be picked up by Friday — which food
> bank near the north side needs it, and who could drive it there?"

## Design principles

- **Grounded, never guessing.** The agent has no built-in knowledge of the
  community's data. It states information only when a tool returned it during
  the current conversation; otherwise it declines with a fixed sentence.
- **Serves groups, not one user.** Cognito identities represent organizations
  (donor / recipient / coordinator), and AVP filters tools per organization.
- **No secrets in code.** Outbound OAuth2 credentials live in the AgentCore
  Identity vault; the agent exchanges its workload identity for a bearer token
  at connection time.
- **Least connection.** Gateways for tools a caller cannot use are never opened,
  so no unnecessary outbound tokens are minted.

## Repository layout

```
.
├── README.md                     # This file
├── amplify.yml                   # AWS Amplify Hosting build spec (publishes static/)
├── docs/
│   └── architecture.drawio       # Editable AWS architecture diagram
├── schemas/                      # OpenAPI + Lambda schemas for gateway targets
│   ├── README.md                 # Detailed schema documentation
│   ├── get-guidelines-lambda.json      # Donation & food-safety guidelines (Lambda)
│   ├── view-surplus-listings-api.json  # Surplus donation listings
│   ├── view-resource-catalog-api.json  # Community resource catalog
│   ├── get-recipient-needs-api.json    # Recipient needs / requests
│   ├── get-pantry-levels-api.json      # Partner pantry stock levels
│   ├── get-volunteer-api.json          # Volunteer drivers
│   └── get-vehicle-api.json            # Vehicles for pickup/delivery
├── backend/                      # Tool implementations + seed data (the tools the agent calls)
│   ├── README.md                 # Backend structure, data model, run + deploy
│   ├── server.py                 # Local dev server (no AWS) exposing every tool
│   ├── lambda_function.py        # AWS Lambda entrypoint (routes by path)
│   ├── template.yaml             # AWS SAM template (Lambda + HTTP API Gateway)
│   ├── samconfig.toml            # SAM deploy defaults (stack name, region)
│   ├── common.py                 # Shared data-loading + response helpers
│   ├── data/                     # Real seed data (resources, surplus, needs, pantry, volunteers, vehicles, guidelines)
│   └── handlers/                 # guidelines · community · pantry · logistics
└── static/                       # Frontend SPA (deploy via Amplify, or S3 + CloudFront)
    ├── index.html                # Login + chat UI + "How it works" panel
    ├── app.js                    # Cognito sign-in + AgentCore/backend calls + rendering
    ├── styles.css                # Animated chat UI styling
    ├── config.js                 # Runtime config (Cognito, AgentCore, BACKEND_API_URL)
    ├── README.md                 # Frontend integration + how-it-works docs
    └── AgentCode/                # The deployable agent (not published to the web)
        ├── agent.py              # Strands agent + AgentCore Runtime entrypoint
        ├── requirements.txt      # Python dependencies
        ├── streamable_http_sigv4.py    # SigV4-signed MCP transport
        ├── streamable_http_oauth2.py   # OAuth2 client-credentials MCP transport
        ├── launchAgent.sh        # End-to-end: venv → deploy → publish frontend
        └── deploy-agentcore-runtime.sh # Configure + launch the AgentCore runtime
```

## Architecture diagram

An editable architecture diagram lives at
[`docs/architecture.drawio`](docs/architecture.drawio). Open it with the
[draw.io desktop app](https://www.drawio.com/), the VS Code *Draw.io Integration*
extension, or [app.diagrams.net](https://app.diagrams.net). It shows the full
flow: browser SPA (Amplify Hosting) → Cognito email-OTP → AgentCore Runtime →
Strands + Claude → AgentCore Gateway (MCP) with Verified Permissions → the
deployed API Gateway + Lambda backend and its data, plus the optional direct
`BACKEND_API_URL` demo path.

## How the agent works

`agent.py` defines a Strands `Agent` fronted by the AgentCore Runtime
(`BedrockAgentCoreApp`). Key points:

- **Model** — Anthropic Claude on Amazon Bedrock, invoked through the Strands
  `BedrockModel`.
- **Tool groups** — the agent registers up to four tool groups, each an MCP
  connection plus the AVP resource ids (gateway target prefixes) it can expose.
  A group is only registered when its gateway URL is configured, so the agent
  runs with any subset of tools deployed. Nothing connects at import time.
- **Per-request connections** — `build_session_tools` opens only the gateways
  the caller is authorized to use, inside an `ExitStack` that stays open for the
  duration of the invocation. Outbound OAuth2 tokens are minted per request.
- **Two-phase authorization** — when an AVP policy store is configured, the
  agent (1) pre-authorizes each group's declared resource ids before connecting,
  then (2) filters the actual tool list to the allowed set after listing tools.
  When AVP is not configured, all registered groups load.

### Tool groups

| Group | Capability | Inbound auth to gateway |
|-------|------------|-------------------------|
| `guidelines` | Donation & food-safety guidelines | AWS IAM (SigV4), execution-role creds |
| `community` | Surplus listings, resource catalog, recipient needs | OAuth2 via AgentCore Identity (M2M) |
| `pantry` | Partner pantry stock levels | OAuth2 via AgentCore Identity (M2M) |
| `logistics` | Volunteers & vehicles | OAuth2 via AgentCore Identity (M2M) |

## Configuration

The agent is configured entirely through environment variables on the AgentCore
runtime. Set only the ones for the tools you deploy; unset groups are skipped.

| Variable | Purpose |
|----------|---------|
| `AWS_REGION` | AWS region (defaults to `us-east-1`) |
| `GUIDELINES_GATEWAY_URL` | MCP URL of the guidelines gateway (SigV4) |
| `COMMUNITY_GATEWAY_URL` | MCP URL of the surplus/catalog/needs gateway |
| `COMMUNITY_OAUTH_PROVIDER` | AgentCore Identity credential-provider name for the community gateway |
| `PANTRY_GATEWAY_URL` | MCP URL of the pantry-levels gateway |
| `PANTRY_OAUTH_PROVIDER` | AgentCore Identity credential-provider name for the pantry gateway |
| `LOGISTICS_GATEWAY_URL` | MCP URL of the volunteers/vehicles gateway |
| `LOGISTICS_OAUTH_PROVIDER` | AgentCore Identity credential-provider name for the logistics gateway |
| `AVP_POLICY_STORE_ID` | Enables per-request AVP tool filtering when set |

OAuth2 client credentials are **not** environment variables — they live in the
AgentCore Identity vault behind the named credential providers above.

## Prerequisites

- The **`bootstrap-stack`** CloudFormation stack deployed (provides the Cognito
  user pool, client, S3 bucket, and CloudFront distribution) and the agent
  execution role.
- AWS credentials with permission to deploy AgentCore.
- Python **3.10+** (the launcher will try to install 3.12 if none is found).
- The **AgentCore CLI** (`agentcore`) available on `PATH`.

## Deploying the agent

From `static/AgentCode`:

```bash
# Full flow: create venv, install deps, configure + launch the runtime,
# then generate and publish the frontend config.js
./launchAgent.sh

# If you already have the dependencies installed:
./launchAgent.sh --skip-venv
```

`launchAgent.sh` calls `deploy-agentcore-runtime.sh`, which:

1. Verifies the AgentCore CLI and AWS credentials.
2. Reads the Cognito user pool / client id from `bootstrap-stack` outputs.
3. Resolves the agent execution role.
4. Runs `agentcore configure` with a **Cognito JWT authorizer** and an
   `Authorization` header allowlist, then `agentcore launch` (agent name
   `good_neighbor_agent`).

After the runtime is deployed, `launchAgent.sh` writes `config.js` (Cognito +
AgentCore Runtime ARN/endpoint) for the frontend, uploads the frontend SPA and
`config.js` to S3, and invalidates the CloudFront cache.

## Frontend

The `static/` directory is a no-build single-page app that lets a community
member sign in and chat with the agent:

1. **Amazon Cognito (passwordless email OTP)** — the user enters their email,
   Cognito emails a one-time code (using its default email — no SES, no Lambda),
   and verifying the code returns a JWT.
2. **AgentCore Runtime** — the SPA calls `InvokeAgentRuntime` over HTTPS with
   the JWT as a `Bearer` token; the runtime's custom JWT authorizer validates
   it (no SigV4 in the browser).
3. **Response** — `agent.py` returns Markdown, which the SPA renders as tables.

The live flow needs the Cognito pool set up for email OTP (enable **Email OTP**,
set email to **Send with Cognito**, allow the **`USER_AUTH`** flow on a public
app client). See [`static/README.md`](static/README.md#enabling-email-otp-on-cognito-one-time-setup-no-ses)
for the exact toggles.

Run it locally with **no AWS** (demo mode with mocked replies) by serving the
folder with any static server:

```bash
cd static
python -m http.server 8000   # open http://localhost:8000
```

When `config.js` still holds placeholder values the app shows a **Demo mode**
badge; after a deploy it shows **Connected to AWS**. See
[`static/README.md`](static/README.md) for the full integration walkthrough and
architecture diagram.

## Backend (tools + data)

The `backend/` directory implements the tools behind the schemas, with real
seed data the agent can reason over (surplus listings cross-referenced to
recipient needs, pantry levels, volunteers, and vehicles). Every tool runs
locally with no AWS via a single stdlib-only server:

```bash
python backend/server.py     # http://localhost:8080
curl "http://localhost:8080/needs?resource_id=RES001"
```

The same handlers deploy to AWS as a single Lambda behind an HTTP API Gateway
using the bundled AWS SAM template:

```bash
cd backend
sam build && sam deploy      # stack: good-neighbor-backend (us-east-1)
```

See [`backend/README.md`](backend/README.md) for the data model, endpoint list,
computed fields, the full deploy/update/teardown steps, and how these endpoints
sit behind AgentCore Gateway targets.

## Schemas

The `schemas/` directory holds the OpenAPI 3.0.3 and Lambda JSON Schema
definitions used to configure AgentCore Gateway targets. See
[`schemas/README.md`](schemas/README.md) for per-file details, the tool-group
mapping, and API usage examples.

## License

Distributed under the **MIT License** — see [`LICENSE`](LICENSE).
Copyright (c) 2026 Dineshraj Dhanapathy@DD.
