# Community Waste Recovery AI Agent

- **Live app:** <https://main.dfwth112aeze8.amplifyapp.com/>
- **Source code:** <https://github.com/dineshrajdhanapathyDD/Community-Waste-Recovery>

## Inspiration

Every day, grocers, restaurants, schools, and households throw away food and
goods that are still perfectly usable — while food banks and shelters just a few
blocks away go short. The problem usually isn't a lack of surplus or a lack of
need; it's that the two are never connected in time, and there's no one to move
things before they spoil. We wanted an assistant that works for a **whole
community** rather than one person: something that can look at who has surplus,
who needs it, what's running low, and who's free to drive — and put those pieces
together fast, safely, and without guessing.

## What it does

The Good Neighbor Agent is a grounded AI assistant that helps a community recover
and redistribute surplus instead of wasting it. You can ask it natural questions
like *"A grocer has 40 lbs of produce that must be picked up by Friday — which
food bank needs it, and who could drive it there?"* and it answers from **real
community data**, not from its own assumptions. It can:

- Look up **surplus donation listings** posted by donors.
- Check **recipient needs** from food banks, shelters, and partners.
- Report **pantry / stock levels** and flag what's running low.
- Find **available volunteers and vehicles** for pickups and deliveries.
- Surface **donation & food-safety guidelines** (acceptance rules, safe windows).
- Browse the shared **community resource catalog**.

Crucially, it's **grounded**: it only states information a tool actually
returned during the conversation — if it doesn't have the data, it says so
instead of inventing an answer.

## How we built it

The project is three deployed pieces that fit together on AWS:

- **Backend (tools + data):** seven tools with real, cross-referenced seed data
  (surplus, needs, pantry, volunteers, vehicles, resources, guidelines). The same
  Python handlers run locally as a stdlib-only server and on AWS as **AWS Lambda
  behind Amazon API Gateway**, deployed with **AWS SAM**.
- **The agent:** a **Strands** agent running on the **Amazon Bedrock AgentCore
  Runtime**, using **Amazon Nova Pro** as the model. It reaches the backend
  through an **AgentCore Gateway (MCP)**, exposing the REST API as tools via an
  OpenAPI target. It authenticates outbound with an OAuth2 token minted by
  **AgentCore Identity**, and is deployed with **AWS IAM (SigV4) inbound auth** —
  no Cognito required for the agent itself.
- **Frontend:** a no-build, animated single-page web app that runs in three
  modes (full agent via Cognito email-OTP, direct-to-backend, or offline demo),
  deployable to **AWS Amplify Hosting**.

End-to-end, a question flows: **Browser → Cognito (JWT) → AgentCore Runtime
(Nova) → AgentCore Gateway (MCP) → API Gateway → Lambda → real data → formatted
answer.**

## Observability & monitoring

Every layer emits logs to **Amazon CloudWatch**, which was essential both for
operating the agent and for debugging the auth chain during the build.

- **AgentCore Runtime logs** — the agent's own stdout/stderr (tool registration,
  each tool call, model responses, tracebacks) land in a dedicated log group:
  ```
  /aws/bedrock-agentcore/runtimes/good_neighbor_agent-<id>-DEFAULT
  ```
  Tail it live while invoking the agent:
  ```bash
  aws logs tail /aws/bedrock-agentcore/runtimes/good_neighbor_agent-<id>-DEFAULT \
    --region us-east-1 --follow
  ```
  These logs surfaced the exact `AccessDenied` messages that told us which IAM
  permission each hop of the runtime → identity → gateway chain needed.

- **AgentCore Gateway logs** — the gateway enables CloudWatch log delivery on
  creation, in its own group:
  ```
  /aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/goodneighborgateway-<id>
  ```
  This is where a tool call could show HTTP 200 while the body was actually an
  "unable to fetch outbound api key" error — the clue that the *gateway's*
  execution role was missing `GetWorkloadAccessToken`.

- **Lambda / API Gateway logs** — the backend function logs to its standard
  `/aws/lambda/good-neighbor-backend` group (per-request output, errors, timing).

- **CodeBuild logs** — each `agentcore deploy` streams its container build
  (QUEUED → PROVISIONING → BUILD → POST_BUILD → COMPLETED) to CloudWatch, so a
  failed image build is diagnosable without local Docker.

- **Traces (optional).** OpenTelemetry tracing on the runtime was disabled
  (`--disable-otel`) to keep the footprint minimal, and the gateway's X-Ray trace
  delivery was left off (logs alone were enough to operate it). Enabling
  OTel / X-Ray is a one-flag change for deeper request tracing later.

**Debugging pattern we relied on:** when the agent misbehaved, we checked the
runtime log group first (was the tool even called?), then — if the tool returned
but the answer was wrong — bypassed the model entirely with a small MCP probe
script (`gateway/probe_tool.py`) to read the raw tool result. Logs told us
*where* it broke; the probe told us *what* the gateway actually returned.

## Challenges we ran into

- **Model access / billing:** our first model choice was gated by an
  `INVALID_PAYMENT_INSTRUMENT` error. We switched to **Amazon Nova Pro**, which
  is served directly by Amazon with no Marketplace subscription — and it worked.
- **Deploying without the original bootstrap stack:** the agent was written to
  expect a Cognito authorizer + a workshop `bootstrap-stack`. We re-architected
  the deploy to use **IAM/SigV4 inbound auth** and a standalone execution role so
  it runs without that stack.
- **A multi-hop auth chain:** wiring the agent to the gateway surfaced a series
  of `AccessDenied` errors, each one hop further along — the invoke needed a
  `--runtime-user-id`, the runtime role needed `GetResourceOauth2Token` and
  Secrets Manager read, and the **gateway** role needed `GetWorkloadAccessToken`
  to fetch its own outbound credential. A direct MCP "probe" script was the key
  to diagnosing each one.
- **The agent over-declining:** even after tools returned real data, a very
  strict "you MUST decline" system prompt made the model refuse. Rebalancing the
  prompt to lead with "use the tool result" fixed it.
- **Windows tooling quirks:** the AgentCore CLI crashed on the console codepage
  (fixed with UTF-8 env vars), and container builds had to run to completion
  uninterrupted.
- **A leaked secret:** a Cognito client secret was hardcoded in helper scripts.
  We moved all credentials to environment variables and documented rotation.

## Accomplishments that we're proud of

- A **fully working end-to-end deployment** on AWS — the live agent answers from
  real backend data, verified with both single-tool and multi-tool questions.
- Getting the **AgentCore Runtime + Gateway + Identity** auth chain working
  **without Cognito or a prebuilt stack**, and documenting every required IAM
  permission so it's reproducible.
- A frontend that **degrades gracefully** across three modes, so it's useful
  whether or not any AWS is deployed — great for demos.
- Honest, accurate documentation and **two architecture diagrams** (plain + AWS
  service icons) that match what's actually running.

## What we learned

- Amazon **Nova** is a clean choice for agents when you want to avoid Marketplace
  subscription/billing friction.
- AgentCore's power comes from its **layered identity model** (workload identity,
  outbound OAuth2 via AgentCore Identity, per-request Verified Permissions) — but
  each layer needs its own explicit IAM permission, and the errors point you
  exactly where.
- A tool-using agent is only as good as its **prompt balance**: too strict and it
  refuses real data; too loose and it hallucinates. "Use the tool result" as the
  dominant instruction, with declining as the rare fallback, is the sweet spot.
- The fastest way to debug an agent is to **call the tool path directly** (bypass
  the model) to separate infrastructure failures from model behavior.

## What's next for Community Waste Recovery AI agent

- **Smarter matching:** guide the agent to map categories (e.g. "produce" →
  tomatoes/carrots) and match vehicles to load size, so multi-tool routing is
  more accurate.
- **Write actions:** move from read-only lookups to letting donors post surplus
  and coordinators confirm pickups.
- **Real data store:** swap the bundled JSON for **Amazon DynamoDB** (the
  volunteer/vehicle schemas already reference the GSIs) for live, multi-org data.
- **Per-organization authorization:** turn on **Amazon Verified Permissions** so
  donors, recipients, and coordinators each see only the tools they should.
- **Notifications & routing:** alert volunteers of nearby pickups and suggest
  efficient routes within food-safety time windows.
- **Production hardening:** add an authorizer to the backend API, rotate secrets
  automatically, and set up CI/CD for the whole stack.


  

## Built with

- **Languages:** Python 3.12; JavaScript, HTML, CSS (no-build SPA)
- **AI / agent:** Amazon Bedrock, Amazon Nova Pro (`us.amazon.nova-pro-v1:0`),
  Amazon Bedrock AgentCore (Runtime · Gateway · Identity), Strands Agents,
  Model Context Protocol (MCP)
- **AWS services:** AWS Lambda, Amazon API Gateway (HTTP API), Amazon Cognito,
  AWS Amplify Hosting (or S3 + CloudFront), AWS IAM, AWS Secrets Manager,
  Amazon Verified Permissions (optional), AWS CodeBuild, Amazon ECR,
  Amazon CloudWatch
- **Infra / tooling:** AWS SAM + CloudFormation, AgentCore starter toolkit/CLI,
  AWS CLI, boto3, OpenAPI 3.0.3 + JSON Schema, draw.io
- **Frontend libs (CDN):** marked (Markdown rendering)

## Testing instructions

You can test at three levels — with zero AWS, with a local backend, or against
the live deployed agent. Pick whichever fits.

### 1. Frontend only, no AWS (fastest — ~10 seconds)

```bash
cd static
python -m http.server 8000
```

Open <http://localhost:8000>. Sign in with **any email** and the code
**`123456`**. The header shows **Demo mode** and replies are mocked — this
verifies the UI, the login flow, and the "How it works" panel.

### 2. Real backend locally, no AWS

Run the tool API and point the frontend at it.

```bash
# terminal 1 — start the backend
python backend/server.py            # http://localhost:8080

# verify it returns real seed data
curl "http://localhost:8080/pantry"
curl "http://localhost:8080/needs?resource_id=RES001"
curl "http://localhost:8080/volunteers?available=true"
```

Then set `BACKEND_API_URL: 'http://localhost:8080'` in `static/config.js`, serve
the frontend as in step 1, sign in with any email + `123456`, and ask
*"What are the current pantry stock levels?"* — the answer is now built from the
real backend (header shows **Live backend data**).

**Expected:** a Markdown table of pantry items with a low-stock flag, e.g. Fresh
tomatoes (8, low), Canned beans (130, ok), Diapers (3, low).

### 3. Live agent on AWS (Amazon Nova via AgentCore)

Requires the AWS CLI configured and the agent deployed (see the root
[`README.md`](../README.md) sections E and F). Invoke the deployed runtime — you
**must** pass `--runtime-user-id`:

```powershell
'{"prompt": "What are the current pantry stock levels? List them."}' | Out-File -Encoding ascii q.json
aws bedrock-agentcore invoke-agent-runtime --region us-east-1 `
  --agent-runtime-arn <RUNTIME_ARN> --runtime-user-id demo-user `
  --payload fileb://q.json --content-type application/json --accept application/json out.json
type out.json
```

**Expected:** `out.json` contains `{"output": {"text": "| ... markdown table
... |"}}` built from live backend data, with `"model": "us.amazon.nova-pro-v1:0"`
in the metadata.

Try a multi-tool question to see the agent orchestrate several tools:

> "A grocer has 40 lbs of fresh produce to pick up by Friday — which food bank
> needs it, which pantry is low, and which available volunteer could drive it?"

### Sample questions to try

- "Show the current surplus donation listings."
- "What are the recipient needs right now?"
- "Which volunteers are available, and what vehicles do we have?"
- "What are the food-safety guidelines for donating prepared meals?"
- "What's low in the pantries?"

### Grounding check (important behavior)

Ask something with **no supporting tool/data**, e.g. *"What's the weather
tomorrow?"* The agent should politely decline rather than answer — it only
responds from tool results, never from general knowledge.

### Debugging the tool path directly

If the live agent declines a data question, call the gateway's MCP endpoint
directly to see the raw tool result (separates an auth/infra issue from model
behavior). Set the gateway env vars from
[`static/AgentCode/gateway/README.md`](../static/AgentCode/gateway/README.md),
then:

```bash
python static/AgentCode/gateway/probe_tool.py
```

**Expected:** it lists the 8 tools and prints the `getPantryLevels` JSON with
`isError: false`.
