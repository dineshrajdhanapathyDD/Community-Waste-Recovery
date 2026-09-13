"""
Probe the gateway's MCP endpoint directly: get an OAuth2 M2M token from the
gateway's Cognito client, list tools, and call getPantryLevels — so we can see
exactly what tool result the agent receives.

Run:  python gateway/probe_tool.py
"""
import json
import os
import sys
import urllib.request
import urllib.parse

# Never hardcode credentials. Supply these via environment variables:
#   GATEWAY_COGNITO_DOMAIN  — https://<domain>.auth.us-east-1.amazoncognito.com
#   GATEWAY_CLIENT_ID       — the Cognito app client id
#   GATEWAY_CLIENT_SECRET   — the Cognito app client secret
#   GATEWAY_MCP_URL         — the gateway's /mcp endpoint URL
#   GATEWAY_SCOPE           — OAuth2 scope (default: GoodNeighborGateway/invoke)
_domain = os.environ.get("GATEWAY_COGNITO_DOMAIN", "")
TOKEN_URL = f"{_domain}/oauth2/token" if _domain else ""
CLIENT_ID = os.environ.get("GATEWAY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GATEWAY_CLIENT_SECRET", "")
SCOPE = os.environ.get("GATEWAY_SCOPE", "GoodNeighborGateway/invoke")
MCP_URL = os.environ.get("GATEWAY_MCP_URL", "")

_missing = [k for k, v in {
    "GATEWAY_COGNITO_DOMAIN": _domain,
    "GATEWAY_CLIENT_ID": CLIENT_ID,
    "GATEWAY_CLIENT_SECRET": CLIENT_SECRET,
    "GATEWAY_MCP_URL": MCP_URL,
}.items() if not v]
if _missing:
    sys.exit("Missing required environment variables: " + ", ".join(_missing))


def get_token():
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": SCOPE,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]


def mcp_call(token, method, params, req_id):
    body = json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}).encode()
    req = urllib.request.Request(MCP_URL, data=body, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    })
    with urllib.request.urlopen(req) as r:
        raw = r.read().decode()
    # Response may be SSE ("data: {...}") or plain JSON.
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"raw": raw}


token = get_token()
print("TOKEN_OK len=", len(token))

tools = mcp_call(token, "tools/list", {}, 1)
names = [t["name"] for t in tools.get("result", {}).get("tools", [])]
print("TOOLS=", names)

result = mcp_call(token, "tools/call",
                  {"name": "BackendTools___getPantryLevels", "arguments": {}}, 2)
print("CALL_RESULT=")
print(json.dumps(result, indent=2)[:2500])
