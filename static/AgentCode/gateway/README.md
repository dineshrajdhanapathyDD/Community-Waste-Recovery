# Gateway wiring scripts

These scripts create and probe the AgentCore Gateway that fronts the
`good-neighbor-backend` API for the agent. See the root
[`README.md`](../../../README.md#f-wire-the-agent-to-the-live-backend-gateway)
for the full flow.

## Credentials come from the environment (never hardcoded)

`create_oauth_provider.py` and `probe_tool.py` read the gateway's Cognito
client credentials from environment variables, so **no secret is committed to
git**. Set them for your shell session before running the scripts.

Fetch the gateway client secret (it's not printed anywhere else):

```bash
aws cognito-idp describe-user-pool-client \
  --user-pool-id <USER_POOL_ID> \
  --client-id <CLIENT_ID> \
  --query "UserPoolClient.ClientSecret" --output text
```

### PowerShell

```powershell
$env:GATEWAY_CLIENT_ID       = "<client id>"
$env:GATEWAY_CLIENT_SECRET   = "<client secret>"
$env:GATEWAY_COGNITO_DOMAIN  = "https://<domain>.auth.us-east-1.amazoncognito.com"
$env:GATEWAY_USER_POOL_ISSUER= "https://cognito-idp.us-east-1.amazonaws.com/<USER_POOL_ID>"
$env:GATEWAY_MCP_URL         = "https://<gateway-id>.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"

python create_oauth_provider.py
python probe_tool.py
```

### bash

```bash
export GATEWAY_CLIENT_ID="<client id>"
export GATEWAY_CLIENT_SECRET="<client secret>"
export GATEWAY_COGNITO_DOMAIN="https://<domain>.auth.us-east-1.amazoncognito.com"
export GATEWAY_USER_POOL_ISSUER="https://cognito-idp.us-east-1.amazonaws.com/<USER_POOL_ID>"
export GATEWAY_MCP_URL="https://<gateway-id>.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"

python create_oauth_provider.py
python probe_tool.py
```

> Tip: keep these in an untracked `set-env.ps1` / `set-env.sh` (both are
> `.gitignore`d) and dot-source it, rather than typing them each time.

## Rotate the secret if it ever leaked

If a client secret was committed at any point, rotate it — a secret in git
history is compromised even after you delete the file:

```bash
# create a new secret-bearing app client, or delete + recreate the gateway's
# Cognito client, then re-run create_oauth_provider.py with the new value.
```

## Files

| File | Purpose |
|------|---------|
| `backend-openapi.json` | Combined OpenAPI spec (7 tools) for the gateway target |
| `create_target.py` | Registers the `openApiSchema` gateway target |
| `create_oauth_provider.py` | Creates the outbound OAuth2 credential provider (env-based) |
| `gateway-workload-policy.json` | IAM the gateway execution role needs |
| `probe_tool.py` | Calls the gateway MCP endpoint directly (debug; env-based) |
