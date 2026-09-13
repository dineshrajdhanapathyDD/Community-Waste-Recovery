"""
Create an AgentCore Identity OAuth2 credential provider that wraps the gateway's
Cognito M2M client. The deployed agent uses this (via
create_streamable_http_transport_agentcore_identity) to mint a bearer token and
call the gateway's MCP endpoint.

Run:  python gateway/create_oauth_provider.py
"""
import json
import os
import sys
import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
PROVIDER_NAME = os.environ.get("GATEWAY_OAUTH_PROVIDER_NAME", "good-neighbor-gateway-oauth")

# Never hardcode credentials. These come from the auto-created gateway Cognito
# authorizer and are supplied via environment variables:
#   GATEWAY_CLIENT_ID       — the Cognito app client id
#   GATEWAY_CLIENT_SECRET   — the Cognito app client secret
#   GATEWAY_COGNITO_DOMAIN  — e.g. https://<domain>.auth.us-east-1.amazoncognito.com
#   GATEWAY_USER_POOL_ISSUER— https://cognito-idp.<region>.amazonaws.com/<poolId>
# Fetch the client secret with:
#   aws cognito-idp describe-user-pool-client --user-pool-id <poolId> \
#       --client-id <clientId> --query "UserPoolClient.ClientSecret" --output text
CLIENT_ID = os.environ.get("GATEWAY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GATEWAY_CLIENT_SECRET", "")
DOMAIN = os.environ.get("GATEWAY_COGNITO_DOMAIN", "")
USER_POOL_ISSUER = os.environ.get("GATEWAY_USER_POOL_ISSUER", "")

_missing = [k for k, v in {
    "GATEWAY_CLIENT_ID": CLIENT_ID,
    "GATEWAY_CLIENT_SECRET": CLIENT_SECRET,
    "GATEWAY_COGNITO_DOMAIN": DOMAIN,
    "GATEWAY_USER_POOL_ISSUER": USER_POOL_ISSUER,
}.items() if not v]
if _missing:
    sys.exit("Missing required environment variables: " + ", ".join(_missing))

client = boto3.client("bedrock-agentcore-control", region_name=REGION)

config = {
    "customOauth2ProviderConfig": {
        "oauthDiscovery": {
            "authorizationServerMetadata": {
                "issuer": USER_POOL_ISSUER,
                "authorizationEndpoint": f"{DOMAIN}/oauth2/authorize",
                "tokenEndpoint": f"{DOMAIN}/oauth2/token",
            }
        },
        "clientId": CLIENT_ID,
        "clientSecret": CLIENT_SECRET,
    }
}

try:
    resp = client.create_oauth2_credential_provider(
        name=PROVIDER_NAME,
        credentialProviderVendor="CustomOauth2",
        oauth2ProviderConfigInput=config,
    )
    print("CREATED")
    print("ARN=" + resp.get("credentialProviderArn", "?"))
    print("NAME=" + resp.get("name", PROVIDER_NAME))
except client.exceptions.ConflictException:
    resp = client.get_oauth2_credential_provider(name=PROVIDER_NAME)
    print("ALREADY_EXISTS")
    print("ARN=" + resp.get("credentialProviderArn", "?"))
    print("NAME=" + resp.get("name", PROVIDER_NAME))
