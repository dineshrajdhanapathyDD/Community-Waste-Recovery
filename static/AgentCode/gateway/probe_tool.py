"""
Probe the gateway's MCP endpoint directly: get an OAuth2 M2M token from the
gateway's Cognito client, list tools, and call getPantryLevels — so we can see
exactly what tool result the agent receives.

Run:  python gateway/probe_tool.py
"""
import json
import urllib.request
import urllib.parse

TOKEN_URL = "https://agentcore-1476ef5b.auth.us-east-1.amazoncognito.com/oauth2/token"
CLIENT_ID = "6l75r1ke77nhcapln9qpc9goaf"
CLIENT_SECRET = "69dludr4u4qifk3n2cs7m5kk26pme2mepgmbsfsh8h2s58f6rnp"
SCOPE = "GoodNeighborGateway/invoke"
MCP_URL = "https://goodneighborgateway-y0bvoowruo.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"


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
