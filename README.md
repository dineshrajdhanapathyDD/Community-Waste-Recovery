# Good Neighbor Agent - Community Waste Recovery

An AI assistant that helps a whole **community** recover and redistribute surplus
instead of throwing it away. It connects people who have surplus (grocers,
restaurants, schools) with people who can use it (food banks, shelters,
neighbors), and routes volunteers and vehicles to move it.

The agent is a [Strands](https://strandsagents.com/) agent running on the
**Amazon Bedrock AgentCore Runtime** using **Amazon Nova Pro**. It reaches its
backend tools through an **AgentCore Gateway** (MCP), and those tools serve real
community data from **AWS Lambda + API Gateway**. A browser SPA lets people sign
in and chat with it.

> **Status:** deployed and verified end to end in AWS (`us-east-1`). Ask the live
> agent "what are the current pantry stock levels?" and it returns a table built
> from real backend data.

## Links

- **Live app:** <https://main.dfwth112aeze8.amplifyapp.com/>
- **Source code:** <https://github.com/dineshrajdhanapathyDD/Community-Waste-Recovery>
- **Project writeup:** [`docs/ABOUT.md`](docs/ABOUT.md) (inspiration, build, challenges, testing)

> The live app runs the frontend on AWS Amplify. Sign in with an email and the
> one-time code to try it. (In demo mode, use code `123456`.)

---

## Table of contents

- [Links](#links)
- [Architecture](#architecture)
- [What it can do](#what-it-can-do)
- [Repository layout](#repository-layout)
- [What to run (by goal)](#what-to-run-by-goal)
  - [A. Just see the UI (no AWS)](#a-just-see-the-ui-no-aws)
  - [B. Run the real backend locally (no AWS)](#b-run-the-real-backend-locally-no-aws)
  - [C. Deploy the backend to AWS](#c-deploy-the-backend-to-aws)
  - [D. Deploy the frontend to AWS Amplify](#d-deploy-the-frontend-to-aws-amplify)
  - [E. Deploy the agent to AgentCore (no Cognito)](#e-deploy-the-agent-to-agentcore-no-cognito)
  - [F. Wire the agent to the live backend (Gateway)](#f-wire-the-agent-to-the-live-backend-gateway)
- [Deployed resources (this account)](#deployed-resources-this-account)
- [How the agent works](#how-the-agent-works)
- [Configuration reference](#configuration-reference)
- [Observability](#observability)
- [Troubleshooting](#troubleshooting)
- [Teardown](#teardown)
- [License](#license)

---

## Architecture

<img width="1536" height="1024" alt="community waste recover  architecture v1" src="https://github.com/user-attachments/assets/34df7e11-8863-4434-829b-435f5efbfcb9" />



```
Browser SPA (static/, Amplify or S3+CloudFront)
      │  sign in + chat
      ▼
Amazon Cognito (email OTP)  ──JWT──▶  AgentCore Runtime  (Amazon Nova Pro)
                                            │  Strands agent (agent.py)
                                            ▼
                                   AgentCore Gateway (MCP)
                                            │  openApiSchema target
                                            ▼
                          API Gateway + Lambda  (backend/, real data)
```


- [`docs/architecture-aws-icons.drawio`](docs/architecture-aws-icons.drawio) -
  official AWS service icons (Amplify, Cognito, Bedrock/AgentCore, API Gateway,
  Lambda, Secrets Manager, IAM, CodeBuild, ECR, CloudWatch). 
- [`docs/architecture.drawio`](docs/architecture.drawio) - simpler plain-box
  version of the same flow.

There are **two ways** the frontend can reach data, and both are built:

- **Direct** - the SPA calls the backend API directly (`BACKEND_API_URL`). Great
  for demos; no agent/LLM involved.
- **Through the agent** - the SPA calls the AgentCore Runtime; the Nova agent
  decides which tools to call via the Gateway and answers in natural language.

---

## What it can do

The agent answers **only** from live tool data (it does not guess). Its tools:

- **Donation & food-safety guidelines** - acceptance rules and safe donation windows.
- **Surplus donation listings** - surplus food/goods posted by donors.
- **Community resource catalog** - categories of items circulating in the network.
- **Recipient needs** - what food banks, shelters, and partners are requesting.
- **Pantry / stock levels** - current stock at partner pantries (with a low-stock flag).
- **Volunteers & vehicles** - available drivers and vehicles for pickups/deliveries.

Example question:

> "A grocer has 40 lbs of produce that must be picked up by Friday - which food
> bank needs it, and who could drive it there?"

---

## Repository layout

```
.
├── README.md                     # This file
├── amplify.yml                   # AWS Amplify Hosting build spec (publishes static/)
├── docs/
│   └── architecture.drawio       # Editable AWS architecture diagram
├── schemas/                      # OpenAPI + Lambda schemas (tool contracts)
├── backend/                      # Tool implementations + real seed data
│   ├── README.md                 # Backend structure, data model, run + deploy
│   ├── server.py                 # Local dev server (no AWS) exposing every tool
│   ├── lambda_function.py        # AWS Lambda entrypoint (routes by path)
│   ├── template.yaml             # AWS SAM template (Lambda + HTTP API Gateway)
│   ├── samconfig.toml            # SAM deploy defaults (stack name, region)
│   ├── common.py                 # Shared data loading + response helpers
│   ├── data/                     # Seed JSON: resources, surplus, needs, pantry, volunteers, vehicles, guidelines
│   └── handlers/                 # guidelines · community · pantry · logistics
└── static/                       # Frontend SPA (deploy via Amplify or S3+CloudFront)
    ├── index.html                # Login + chat UI + "How it works" panel
    ├── app.js                    # Cognito sign-in + AgentCore/backend calls + rendering
    ├── styles.css                # Animated chat UI
    ├── config.js                 # Runtime config (Cognito, AgentCore, BACKEND_API_URL)
    ├── README.md                 # Frontend + Amplify deploy docs
    └── AgentCode/                # The deployable agent (NOT published to the web)
        ├── agent.py              # Strands agent + AgentCore Runtime entrypoint (Amazon Nova)
        ├── requirements.txt      # Python dependencies (strands-agents pinned)
        ├── deploy-agent-noauth.ps1     # Deploy the agent with IAM auth (no Cognito)
        ├── iam/                        # Standalone execution role trust + permissions
        ├── gateway/                    # Scripts to wire the Gateway to the backend
        │   ├── backend-openapi.json    # Combined OpenAPI spec for the 7 tools
        │   ├── create_target.py        # Create the openApiSchema gateway target
        │   ├── create_oauth_provider.py# Create the outbound OAuth2 provider
        │   ├── gateway-workload-policy.json # IAM the gateway role needs
        │   └── probe_tool.py           # Call the gateway's MCP endpoint directly (debug)
        ├── launchAgent.sh              # Cognito/bootstrap-stack flow (alternative)
        └── deploy-agentcore-runtime.sh # Cognito configure + launch (used by launchAgent.sh)
```

---

## What to run (by goal)

Pick the goal you want. A → F increase in scope; each stands on its own.

### A. Just see the UI (no AWS)

Only needs Python.

```bash
cd static
python -m http.server 8000
# open http://localhost:8000 - sign in with any email + code 123456
```

Runs in **Demo mode** (mocked replies) so you can explore the animated UI and the
"How it works" panel. Motion respects `prefers-reduced-motion`.

### B. Run the real backend locally (no AWS)

The backend is stdlib-only Python - nothing to install.

```bash
# terminal 1 - start the tools API
python backend/server.py                       # http://localhost:8080
curl "http://localhost:8080/pantry"            # real seed data

# then point the SPA at it: in static/config.js set
#   BACKEND_API_URL: 'http://localhost:8080',
# and serve the frontend as in step A.
```

The SPA badge switches to **Live backend data** and answers come from the real
handlers + seed data. See [`backend/README.md`](backend/README.md) for the data
model and every endpoint.

### C. Deploy the backend to AWS

Needs the **AWS CLI** and **AWS SAM CLI** with credentials configured.

```bash
cd backend
sam build
sam deploy            # creates CloudFormation stack: good-neighbor-backend (us-east-1)
```

Copy the `ApiBaseUrl` output into `static/config.js` as `BACKEND_API_URL`. The
frontend now talks to your live AWS backend (Lambda + HTTP API Gateway).

### D. Deploy the frontend to AWS Amplify

Push this repo to Git, then in the **Amplify console**: *New app → Host web app →
connect the repo → deploy*. Amplify auto-detects [`amplify.yml`](amplify.yml)
(which publishes `static/` and prunes the backend `AgentCode/` from the web
root). To inject `config.js` from Amplify env vars instead of committing it, see
the commented block in `amplify.yml`.

### E. Deploy the agent to AgentCore (no Cognito)

This runs the Strands agent on **AgentCore Runtime** with **Amazon Nova Pro**,
using **AWS IAM (SigV4)** inbound auth - no Cognito, no `bootstrap-stack`.

Prerequisites:

- `pip install bedrock-agentcore-starter-toolkit` (gives the `agentcore` CLI)
- **Bedrock model access** for Amazon Nova in your region (Nova needs no
  Marketplace subscription, so no payment-instrument gate)
- A standalone execution role - the trust + permissions JSON is in
  [`static/AgentCode/iam/`](static/AgentCode/iam)

```powershell
cd static/AgentCode
# Windows: force UTF-8 so the CLI's console output doesn't crash on cp1252
$env:PYTHONUTF8=1; $env:PYTHONIOENCODING="utf-8"
powershell -ExecutionPolicy Bypass -File .\deploy-agent-noauth.ps1
```

The script runs `agentcore configure` (no `--authorizer-config` → IAM auth) then
`agentcore deploy` (builds the ARM64 container remotely via CodeBuild — no local
Docker). Invoke it (pass a `--runtime-user-id`; see below why):

```powershell
'{"prompt": "hello"}' | Out-File -Encoding ascii payload.json
aws bedrock-agentcore invoke-agent-runtime --region us-east-1 `
  --agent-runtime-arn <RUNTIME_ARN> --runtime-user-id demo-user `
  --payload fileb://payload.json --content-type application/json --accept application/json out.json
```

> There is also a Cognito-based path (`launchAgent.sh` + `deploy-agentcore-runtime.sh`)
> that uses a `bootstrap-stack` for the Cognito pool, S3, and CloudFront. Use the
> no-Cognito path above unless you already have that stack.

### F. Wire the agent to the live backend (Gateway)

This is what makes the agent answer from **real** data instead of only its own
reasoning. The backend REST API is fronted by an **AgentCore Gateway** exposed to
the agent over MCP.

```bash
# 1. Create the gateway (auto-creates a Cognito authorizer + gateway role)
agentcore gateway create-mcp-gateway --region us-east-1 --name GoodNeighborGateway

# 2. Register the backend as an MCP tool target (edit IDs in the script first)
python static/AgentCode/gateway/create_target.py

# 3. Create the outbound OAuth2 provider the agent uses to call the gateway
python static/AgentCode/gateway/create_oauth_provider.py

# 4. Point the runtime at the gateway and redeploy
cd static/AgentCode
agentcore deploy --auto-update-on-conflict `
  --env COMMUNITY_GATEWAY_URL=<gateway mcp url> `
  --env COMMUNITY_OAUTH_PROVIDER=good-neighbor-gateway-oauth
```

Then invoke with a data question (again, pass `--runtime-user-id`):

```powershell
'{"prompt": "What are the current pantry stock levels?"}' | Out-File -Encoding ascii q.json
aws bedrock-agentcore invoke-agent-runtime --region us-east-1 `
  --agent-runtime-arn <RUNTIME_ARN> --runtime-user-id demo-user `
  --payload fileb://q.json --content-type application/json --accept application/json out.json
```

The agent returns a Markdown table of the live pantry data plus a summary.

**Why `--runtime-user-id`?** The runtime uses IAM (SigV4) inbound auth, so the
outbound machine-to-machine token flow (AgentCore Identity) needs a workload
identity - the user id supplies it. Without it you get *"Workload access token
has not been set."*

**Debugging:** [`gateway/probe_tool.py`](static/AgentCode/gateway/probe_tool.py)
calls the gateway's MCP endpoint directly (token → list tools → call one), so you
can see the exact tool result the agent receives. This is the fastest way to tell
an auth failure apart from a model-behavior issue.

---

## Deployed resources (this account)

For reference, what a full deploy created in `us-east-1` (account `466742534146`):

| Resource | Identifier |
|----------|------------|
| Backend stack | `good-neighbor-backend` (Lambda + HTTP API) |
| Backend API URL | `https://h1aly0x3a1.execute-api.us-east-1.amazonaws.com` |
| Agent runtime | `good_neighbor_agent-m0NZWbGrv5` (Amazon Nova Pro, IAM auth) |
| Runtime exec role | `good-neighbor-agent-exec-role` |
| Gateway | `goodneighborgateway-y0bvoowruo` |
| Gateway target | `BackendTools` (openApiSchema → backend API) |
| Gateway exec role | `AgentCoreGatewayExecutionRole` |
| Outbound OAuth2 provider | `good-neighbor-gateway-oauth` |

---

## How the agent works

`agent.py` defines a Strands `Agent` fronted by the AgentCore Runtime
(`BedrockAgentCoreApp`).

- **Model** - Amazon Nova Pro (`us.amazon.nova-pro-v1:0`) via the Strands
  `BedrockModel`. Amazon's own model family, so no Marketplace subscription is
  needed (avoids the `INVALID_PAYMENT_INSTRUMENT` gate that third-party models
  can hit).
- **Tool groups** - the agent registers a tool group only when its gateway URL is
  configured, so it runs with any subset of tools. Nothing connects at import
  time; connections open per request. In the current deploy the **community**
  group is wired to the Gateway, and that one Gateway exposes all backend tools.
- **Grounded** - the system prompt leads with "use the tool result": when a tool
  returns data the agent must present it (Markdown table + summary); it declines
  only when no tool can serve the request.
- **Optional AVP** - if `AVP_POLICY_STORE_ID` is set, tools are filtered per
  request against the caller's identity via Amazon Verified Permissions; unset,
  all registered groups load.

## Live AWS Agent - Amazon Nova + AgentCore
  With the deployed AWS environment, invoke the AgentCore runtime using --runtime-user-id demo-user.

  Test questions such as:
  - “Show current surplus donations.”

<img width="1917" height="911" alt="Screenshot 2026-09-14 092917" src="https://github.com/user-attachments/assets/dff0116f-1614-4141-88b0-6119caabbf03" />

    
  - “Which volunteers are available?”
<img width="1759" height="655" alt="Screenshot 2026-09-14 092933" src="https://github.com/user-attachments/assets/d6c1e9f1-e0c3-452b-b1e7-e9ec1b843182" />


  - “What are the current pantry stock levels?”
<img width="1753" height="693" alt="Screenshot 2026-09-14 092953" src="https://github.com/user-attachments/assets/b4bae9b6-4fe6-4bcd-b3bb-d6cfdaa8fdd0" />


  - “Which food bank needs the available produce?”
<img width="1766" height="622" alt="Screenshot 2026-09-14 093008" src="https://github.com/user-attachments/assets/b57e9298-2258-482c-847d-c5543e6c60b3" />


  Grounding Test: Ask an unrelated question such as “What’s the weather tomorrow?” The agent should decline because it only answers from verified tool data.
<img width="1105" height="336" alt="Screenshot 2026-09-14 093023" src="https://github.com/user-attachments/assets/0d48f51c-8b21-4472-b1fc-4a2bd3831995" />


  

---

## Configuration reference

Agent runtime environment variables (set via `agentcore deploy --env KEY=VALUE`):

| Variable | Purpose |
|----------|---------|
| `AWS_REGION` | AWS region (default `us-east-1`) |
| `COMMUNITY_GATEWAY_URL` | MCP URL of the gateway the agent calls |
| `COMMUNITY_OAUTH_PROVIDER` | AgentCore Identity provider name for the gateway |
| `GUIDELINES_GATEWAY_URL` | (optional) separate guidelines gateway (SigV4) |
| `PANTRY_GATEWAY_URL` / `PANTRY_OAUTH_PROVIDER` | (optional) separate pantry gateway |
| `LOGISTICS_GATEWAY_URL` / `LOGISTICS_OAUTH_PROVIDER` | (optional) separate logistics gateway |
| `AVP_POLICY_STORE_ID` | (optional) enables per-request AVP tool filtering |

Frontend config (`static/config.js`, `window.WORKSHOP_CONFIG`):

| Key | Purpose |
|-----|---------|
| `BACKEND_API_URL` | Deployed backend API - SPA answers directly from it |
| `COGNITO_USER_POOL_ID` / `COGNITO_CLIENT_ID` / `COGNITO_REGION` | Cognito email-OTP sign-in |
| `AGENTCORE_RUNTIME_ARN` / `AGENTCORE_ENDPOINT` | Call the agent runtime from the browser |

IAM permissions the wiring requires (each otherwise surfaces as
`AccessDeniedException`):

- **Runtime role** (`good-neighbor-agent-exec-role`): Bedrock invoke,
  `bedrock-agentcore:GetResourceOauth2Token`, `GetWorkloadAccessToken*`, and
  `secretsmanager:GetSecretValue` on `bedrock-agentcore-identity!default/*`.
- **Gateway role** (`AgentCoreGatewayExecutionRole`):
  `bedrock-agentcore:GetWorkloadAccessToken` + `GetResourceApiKey` — see
  [`gateway/gateway-workload-policy.json`](static/AgentCode/gateway/gateway-workload-policy.json).

---

## Observability

Every layer logs to **Amazon CloudWatch**. Log groups:

| Component | CloudWatch log group |
|-----------|----------------------|
| AgentCore Runtime | `/aws/bedrock-agentcore/runtimes/good_neighbor_agent-<id>-DEFAULT` |
| AgentCore Gateway | `/aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/goodneighborgateway-<id>` |
| Backend Lambda | `/aws/lambda/good-neighbor-backend` |
| Container build | CodeBuild build logs (per `agentcore deploy`) |

Tail the agent live while invoking it:

```bash
aws logs tail /aws/bedrock-agentcore/runtimes/good_neighbor_agent-<id>-DEFAULT \
  --region us-east-1 --follow
```

The runtime log shows tool registration, each tool call, the model response, and
full tracebacks — this is where the auth-chain `AccessDenied` errors surfaced.
The gateway log is where a tool call can show HTTP 200 while the body is an
"unable to fetch outbound api key" error (missing gateway permission).

Tracing is off by default: the runtime is deployed with `--disable-otel` and the
gateway's X-Ray trace delivery is left disabled (logs are enough to operate it).
Enabling OpenTelemetry / X-Ray is a one-flag change for deeper request tracing.

> Tip: to inspect a tool result without the model, run
> [`gateway/probe_tool.py`](static/AgentCode/gateway/probe_tool.py) — logs tell
> you *where* a request broke, the probe tells you *what* the gateway returned.

---

## Troubleshooting

- **Agent replies "I'm not able to help…" for data questions** - the tool
  returned an error or the prompt is over-declining. Run `gateway/probe_tool.py`
  to see the raw tool result. If it shows *"unable to fetch outbound api key"*,
  the gateway role is missing `GetWorkloadAccessToken`/`GetResourceApiKey`.
- **"Workload access token has not been set"** - invoke with `--runtime-user-id`.
- **`INVALID_PAYMENT_INSTRUMENT`** - you're on a third-party model; switch to
  Amazon Nova or add a payment method + enable the model in Bedrock.
- **`agentcore` CLI crashes with a `UnicodeEncodeError` on Windows** - set
  `$env:PYTHONUTF8=1; $env:PYTHONIOENCODING="utf-8"` first.
- **`agentcore deploy` seems to hang / stops mid-build** - let it run to
  completion (it monitors CodeBuild); use `--auto-update-on-conflict` to update
  an existing runtime.
- **SAM CLI shows a non-zero exit on Windows** - its progress banner goes to
  stderr; trust the textual `Successfully created/updated stack` result.

---

## Teardown

Remove everything a full deploy created (stops any charges):

```bash
# Backend (Lambda + API Gateway)
sam delete --stack-name good-neighbor-backend --region us-east-1

# Agent runtime
agentcore destroy

# Gateway + target, OAuth2 provider, and the IAM roles/Cognito pool the gateway
# auto-created are removed via the console or the bedrock-agentcore-control API.
```

---

## License

Distributed under the **MIT License** - see [`LICENSE`](LICENSE).
Copyright (c) 2026 Dineshraj Dhanapathy@DD.
