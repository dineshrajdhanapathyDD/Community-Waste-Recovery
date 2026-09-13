"""
Create an openApiSchema target on the Good Neighbor AgentCore gateway that
points at the deployed good-neighbor-backend HTTP API.

The backend is open (no auth), but AgentCore's openApiSchema target still
requires a credential provider, so we attach a dummy API-key header the backend
simply ignores.

Run:  python gateway/create_target.py
"""
import json
import os

from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

REGION = "us-east-1"
GATEWAY_ID = "goodneighborgateway-y0bvoowruo"
HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "backend-openapi.json"), "r", encoding="utf-8") as fh:
    openapi_spec = fh.read()

client = GatewayClient(region_name=REGION)

# Fetch the existing gateway so we have its id + roleArn (shape the toolkit wants).
gw = client.client.get_gateway(gatewayIdentifier=GATEWAY_ID)
gateway = {"gatewayId": gw["gatewayId"], "roleArn": gw["roleArn"]}

target = client.create_mcp_gateway_target(
    gateway=gateway,
    name="BackendTools",
    target_type="openApiSchema",
    target_payload={"inlinePayload": openapi_spec},
    # Dummy API key — the open backend ignores the header. Required because the
    # toolkit always provisions a credential provider for openApiSchema targets.
    credentials={
        "api_key": "not-used-open-backend",
        "credential_location": "HEADER",
        "credential_parameter_name": "X-Api-Key",
    },
)

print("TARGET_ID=" + target.get("targetId", "?"))
print("STATUS=" + target.get("status", "?"))
print(json.dumps(target, default=str)[:800])
