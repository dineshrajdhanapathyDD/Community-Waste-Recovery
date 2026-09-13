"""
Create an AgentCore Identity OAuth2 credential provider that wraps the gateway's
Cognito M2M client. The deployed agent uses this (via
create_streamable_http_transport_agentcore_identity) to mint a bearer token and
call the gateway's MCP endpoint.

Run:  python gateway/create_oauth_provider.py
"""
import json
import boto3

REGION = "us-east-1"
PROVIDER_NAME = "good-neighbor-gateway-oauth"

# From the auto-created gateway Cognito authorizer.
CLIENT_ID = "6l75r1ke77nhcapln9qpc9goaf"
CLIENT_SECRET = "69dludr4u4qifk3n2cs7m5kk26pme2mepgmbsfsh8h2s58f6rnp"
DOMAIN = "https://agentcore-1476ef5b.auth.us-east-1.amazoncognito.com"
USER_POOL_ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_munIQlezO"

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
