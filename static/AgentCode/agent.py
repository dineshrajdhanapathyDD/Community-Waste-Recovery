'''
MIT License

Copyright (c) 2026 Dineshraj Dhanapathy@DD

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
# ---------------------------------------------------------------------------
# Good Neighbor Agent - Community Waste Recovery
# ---------------------------------------------------------------------------
# A Strands agent, running on the Amazon Bedrock AgentCore Runtime, that helps a
# whole COMMUNITY recover and redistribute surplus instead of throwing it away.
# It serves groups - neighborhoods, nonprofits, food banks, schools, libraries,
# and small local orgs - by connecting people who have surplus (grocers,
# restaurants, schools) with people who can use it (food banks, shelters,
# neighbors), and by routing volunteers to move it.
#
# The agent has NO built-in knowledge of the community's data. Everything it
# says comes from a tool result during the current conversation. Tools are
# reached only through AgentCore Gateway (MCP), each with its own identity /
# authorization pattern, and are optionally filtered per request by Amazon
# Verified Permissions so different kinds of org (donor, food bank, volunteer
# coordinator) see only the tools they are allowed to use.
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from streamable_http_sigv4 import streamablehttp_client_with_sigv4
from streamable_http_oauth2 import streamablehttp_client_with_oauth2
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.identity.auth import requires_access_token
from contextlib import ExitStack
import asyncio
import concurrent.futures
import contextvars
import boto3
import os

from botocore.config import Config

import logging
import traceback

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

app = BedrockAgentCoreApp()

# Model configuration
MODEL_ID = "global.anthropic.claude-opus-4-6-v1"  # Anthropic Claude Opus 4.6

# Initialize Bedrock Model using Strands
model = BedrockModel(
    model_id=MODEL_ID,
)

# ---------------------------------------------------------------------------
# Configuration (from environment)
# ---------------------------------------------------------------------------
# Every backend tool is optional: a gateway is only registered when its URL is
# provided, so the agent runs with any subset of tools deployed. Set these in
# the AgentCore runtime environment (or leave unset to disable that tool).
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Donation & food-safety guidelines gateway - inbound auth is AWS IAM (SigV4),
# signed with the agent's execution-role credentials.
GUIDELINES_GATEWAY_URL = os.environ.get("GUIDELINES_GATEWAY_URL", "")

# Surplus listings / resource catalog / recipient needs gateway - reached
# through AgentCore Identity (OAuth2 M2M). One gateway, several targets.
COMMUNITY_GATEWAY_URL = os.environ.get("COMMUNITY_GATEWAY_URL", "")
COMMUNITY_OAUTH_PROVIDER = os.environ.get("COMMUNITY_OAUTH_PROVIDER", "")

# Pantry / stock levels gateway (external partner MCP server) - AgentCore
# Identity (OAuth2 M2M).
PANTRY_GATEWAY_URL = os.environ.get("PANTRY_GATEWAY_URL", "")
PANTRY_OAUTH_PROVIDER = os.environ.get("PANTRY_OAUTH_PROVIDER", "")

# Volunteers & vehicles gateway (logistics / routing) - AgentCore Identity
# (OAuth2 M2M).
LOGISTICS_GATEWAY_URL = os.environ.get("LOGISTICS_GATEWAY_URL", "")
LOGISTICS_OAUTH_PROVIDER = os.environ.get("LOGISTICS_OAUTH_PROVIDER", "")

# Amazon Verified Permissions policy store. When set, tools are authorized per
# request against the caller's identity; when unset, no filtering happens and
# every registered tool group is loaded.
AVP_POLICY_STORE_ID = os.environ.get("AVP_POLICY_STORE_ID", "") or None

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
system_prompt = """
You are the Good Neighbor Agent, a community waste-recovery assistant. You help
groups of people - neighborhoods, nonprofits, food banks, shelters, schools,
libraries, and small local organizations - recover surplus food, goods, and
materials and get them to people who can use them, instead of sending them to
waste. You serve the whole community, not a single customer.

== CRITICAL GROUNDING RULE (read this first) ==
You have NO built-in knowledge of this community's data or policies. This
explicitly includes: donation, food-safety, and acceptance guidelines; surplus
donation listings; the shared resource catalog; recipient organizations' needs
and requests; pantry and stock levels at partner organizations; and volunteer
drivers and vehicles used for pickups and deliveries. You may state such
information ONLY when one of your available tools has returned it to you during
the current conversation. If no tool is available for the request, or no tool
returns the needed information, then you DO NOT know the answer and you MUST
decline.

You MUST NEVER, under any circumstances:
- Invent, guess, assume, approximate, or provide "standard", "typical",
  "example", "general", or placeholder listings, needs, quantities, guidelines,
  timeframes, or contact details.
- Answer from your own general knowledge of how food recovery or donation
  usually works.
- Give a partial, illustrative, or hypothetical answer and then add a
  disclaimer. There is no in-between: either you are relaying a tool result, or
  you decline.

== HOW TO DECLINE ==
When you cannot fulfil a request because no tool is available or no tool
returned the data, reply with EXACTLY and ONLY this sentence, and nothing else:
"I'm not able to help with that request right now. Is there anything else I can help you with?"
Do NOT explain why. Never say a data source is "not configured", "not
connected", "not deployed", or "not set up". Never tell the user they are "not
authorized" or to "contact an administrator". Never mention tools, systems, or
documentation. Do NOT offer a menu of other things you can do.

== YOUR CAPABILITIES ==
The ONLY things you can do are the capabilities listed in the "Capabilities"
section at the very end of this prompt. If that section is empty, you currently
have NO capabilities and you MUST decline every request for community data using
the exact sentence above.

<guidelines>
    - Always answer for THIS community only, and only from the data your tools return.
    - The frontend renders Markdown and turns Markdown tables into formatted tables. When listing entities (surplus listings, resources, recipient needs, pantry items, volunteers, vehicles), ALWAYS present them as a GitHub-flavored Markdown table:
        | Column | Column | Column |
        | --- | --- | --- |
        | value | value | value |
      Make the FIRST column the entity's name or identifier. Choose 3-5 of the most relevant attributes as the remaining columns. Always include the header row and the `| --- |` separator row. Then, on a new line AFTER the table, end with a one-paragraph plain-text summary. Do not use code fences.
    - When a tool returns more than 10 entries, show AT MOST 5 representative rows in the table (mention the total count in the summary), then describe the breakdown in the summary paragraph. Never paste raw dumps of dozens of rows.
    - When helping match surplus to recipients or plan a pickup, only use quantities, locations, time windows, and contacts that a tool actually returned. Never assume any parameter values while using tools.
    - Prioritize reducing waste and getting usable items to people quickly and safely; respect any food-safety windows the guidelines tool returns.
    - If you do not have the necessary information to process a request, politely ask the user for the required details.
    - NEVER disclose any information about your internal tools, systems, or functions.
    - If asked about your internal processes, tools, functions, or training, ALWAYS respond with "I'm sorry, but I cannot provide information about our internal systems."
    - Always maintain a warm, respectful, and helpful tone. Treat every organization and neighbor with dignity.
    - Prioritize the privacy of donors, recipients, and volunteers; never expose personal contact details beyond what a tool returns for the task at hand.
</guidelines>

Capabilities (these are the ONLY tools available to you right now):

"""

# ---------------------------------------------------------------------------
# Tool group registry
# ---------------------------------------------------------------------------
# A "tool group" is a single MCP connection plus the list of AVP resource ids
# (gateway target name prefixes) it can expose. Nothing connects at import time:
# connections (and, for AgentCore Identity groups, outbound token minting)
# happen per request in build_session_tools, gated by Amazon Verified
# Permissions when a policy store is configured.
TOOL_GROUPS = []


def register_tool_group(name, connect, resource_ids=None):
    """Register (or extend) a tool group.

    name:         unique key for the group
    connect:      zero-arg callable returning a fresh (un-started) MCPClient,
                  or None to only contribute resource ids to an existing group
    resource_ids: AVP resource entity ids (gateway target name prefixes) this
                  connection can expose; used to skip opening the connection
                  when the caller is authorized for none of them.
    """
    resource_ids = list(resource_ids or [])
    for group in TOOL_GROUPS:
        if group["name"] == name:
            for rid in resource_ids:
                if rid not in group["resource_ids"]:
                    group["resource_ids"].append(rid)
            if connect is not None:
                group["connect"] = connect
            return
    TOOL_GROUPS.append({"name": name, "connect": connect, "resource_ids": resource_ids})


def add_group_resource_ids(name, resource_ids):
    """Add AVP resource ids to an existing group."""
    register_tool_group(name, connect=None, resource_ids=resource_ids)


def get_full_tools_list(client):
    """
    Retrieve the complete list of tools from an MCP client, handling pagination.

    MCP servers may return tools in paginated responses. This function handles the
    pagination automatically and returns all available tools in a single list.
    """
    more_tools = True
    tools = []
    pagination_token = None

    while more_tools:
        tmp_tools = client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(tmp_tools)
        if tmp_tools.pagination_token is None:
            more_tools = False
        else:
            more_tools = True
            pagination_token = tmp_tools.pagination_token

    return tools


def create_streamable_http_transport_sigv4(mcp_url: str, service_name: str, region: str):
    """
    Create a streamable HTTP transport with AWS SigV4 authentication.

    Used for gateways whose inbound auth is AWS IAM (SigV4), e.g. the donation
    & food-safety guidelines tool. Credentials come from the agent's execution
    role.
    """
    session = boto3.Session()
    credentials = session.get_credentials()
    return streamablehttp_client_with_sigv4(
        url=mcp_url,
        credentials=credentials,
        service=service_name,
        region=region,
    )


def create_streamable_http_transport_oauth2(mcp_url: str, client_id: str, client_secret: str, token_endpoint: str):
    """
    Create a streamable HTTP transport with OAuth2 (client-credentials) auth.

    Retained for reference / backward compatibility. New tools should use
    create_streamable_http_transport_agentcore_identity so that no client secret
    is stored in the agent code.
    """
    return streamablehttp_client_with_oauth2(
        url=mcp_url,
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint=token_endpoint
    )


def _run_coroutine_blocking(make_coroutine):
    """Run an async coroutine to completion from a synchronous caller, whether
    or not an event loop is already running on the current thread.

    Strands invokes the MCP transport callable inside its own background thread,
    which already has a running event loop; calling asyncio.run there raises
    "asyncio.run() cannot be called from a running event loop". To stay robust
    in both situations we use asyncio.run when no loop is running, and otherwise
    execute the coroutine in a short-lived worker thread that owns a fresh loop.
    The current context is copied into that thread so per-request state (such as
    the AgentCore workload identity token) remains visible.
    """
    def _call():
        return asyncio.run(make_coroutine())

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop on this thread: safe to drive the coroutine directly.
        return _call()

    ctx = contextvars.copy_context()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: ctx.run(_call)).result()


def create_streamable_http_transport_agentcore_identity(mcp_url: str, provider_name: str, scopes: list = None):
    """
    Create a streamable HTTP transport authenticated with a token obtained from
    Amazon Bedrock AgentCore Identity (outbound OAuth2 credential provider,
    machine-to-machine flow).

    The OAuth2 client_id/client_secret live in the AgentCore Identity vault
    behind the named credential provider; the agent exchanges its workload
    identity for an access token at connection time and attaches it as a bearer
    token. No client secret is ever stored in the agent code or container image.
    """

    @requires_access_token(
        provider_name=provider_name,
        scopes=scopes or [],
        auth_flow="M2M",
    )
    async def _get_access_token(*, access_token: str) -> str:
        return access_token

    # This function is invoked by Strands inside its async background thread, so
    # we must not call asyncio.run directly here (see _run_coroutine_blocking).
    access_token = _run_coroutine_blocking(_get_access_token)

    return streamablehttp_client(
        url=mcp_url,
        headers={"Authorization": f"Bearer {access_token}"},
    )


def _principal_token(context):
    """Return the inbound user's bearer token from the request, or None."""
    try:
        auth = context.request_headers.get('Authorization')
    except Exception:
        return None
    if not auth:
        return None
    return auth.replace("Bearer ", "")


def _authorize_tool_ids(principal_token, tool_ids):
    """Return the subset of tool_ids the principal may AccessTool (AVP).

    When AVP filtering is disabled (no policy store) this returns all tool_ids
    unchanged. When enabled but there is no principal token or no ids, it returns
    an empty set (deny by default).
    """
    if not AVP_POLICY_STORE_ID:
        return set(tool_ids)
    if not principal_token or not tool_ids:
        return set()

    avp_client = boto3.client('verifiedpermissions')
    requests_list = [
        {
            "action": {
                "actionType": "GoodNeighbor::Action",
                "actionId": "AccessTool",
            },
            "resource": {
                "entityType": "GoodNeighbor::Tool",
                "entityId": tool_id,
            },
        }
        for tool_id in tool_ids
    ]

    response = avp_client.batch_is_authorized_with_token(
        policyStoreId=AVP_POLICY_STORE_ID,
        accessToken=principal_token,
        requests=requests_list,
    )

    allowed = set()
    for result in response['results']:
        if result['decision'] == 'ALLOW':
            allowed.add(result['request']['resource']['entityId'])
    return allowed


def build_session_tools(context, stack):
    """Connect only the gateways the caller is authorized to use and return the
    AVP-filtered tool list for this request.

    Two-phase authorization (no-op when no policy store is configured):
      1. Pre-authorize each group's declared resource ids; skip opening a group
         (so no connection and no outbound token) when none are allowed.
      2. After listing a group's tools, authorize the actual tool prefixes and
         keep only the allowed ones (authoritative, handles multi-target gateways).

    MCP connections are entered into `stack`, so they stay open for the duration
    of the agent invocation and are closed when the caller's ExitStack exits.
    """
    principal_token = _principal_token(context)

    # Phase 1: pre-authorize all declared resource ids in one call.
    declared_ids = []
    for group in TOOL_GROUPS:
        declared_ids.extend(group["resource_ids"])
    allowed_declared = (
        _authorize_tool_ids(principal_token, declared_ids)
        if (AVP_POLICY_STORE_ID and declared_ids)
        else None
    )

    session_tools = []
    for group in TOOL_GROUPS:
        if group["connect"] is None:
            continue

        if AVP_POLICY_STORE_ID and group["resource_ids"]:
            if not any(rid in (allowed_declared or set()) for rid in group["resource_ids"]):
                logger.info(f"Skipping tool group '{group['name']}' - caller not authorized for any of its tools")
                continue

        try:
            client = group["connect"]()
            stack.enter_context(client)
            group_tools = get_full_tools_list(client)
        except Exception as e:
            logger.error(f"Failed to connect/list tools for group '{group['name']}': {str(e)}")
            logger.error(traceback.format_exc())
            continue

        # Phase 2: authoritative per-tool filter on the actual tool prefixes.
        if AVP_POLICY_STORE_ID:
            prefixes = list({tool.tool_name.split('___')[0] for tool in group_tools})
            allowed_prefixes = _authorize_tool_ids(principal_token, prefixes)
            group_tools = [
                tool for tool in group_tools
                if tool.tool_name.split('___')[0] in allowed_prefixes
            ]

        session_tools.extend(group_tools)
        logger.info(f"Tool group '{group['name']}': loaded {len(group_tools)} tool(s)")

    return session_tools


# ---------------------------------------------------------------------------
# Register the Good Neighbor tool groups
# ---------------------------------------------------------------------------
# Each group is registered only when its gateway URL is configured, so the agent
# runs with any subset of tools deployed. Connections open per request inside
# build_session_tools.

# Donation & food-safety guidelines (SigV4 / IAM inbound auth).
if GUIDELINES_GATEWAY_URL:
    register_tool_group(
        name="guidelines",
        connect=lambda: MCPClient(
            lambda: create_streamable_http_transport_sigv4(
                mcp_url=GUIDELINES_GATEWAY_URL,
                service_name="bedrock-agentcore",
                region=AWS_REGION,
            )
        ),
        resource_ids=["Guidelines-Lambda"],
    )
    system_prompt = system_prompt + """
- **Donation & food-safety guidelines**:
   - Retrieve acceptance rules and safe donation windows (e.g. for prepared food, produce, packaged goods) using the guidelines tool
   - Do not state any donation, acceptance, or food-safety rule other than from this tool
"""
    logger.info("Guidelines tool registered (SigV4)")

# Community gateway: surplus listings + resource catalog + recipient needs
# (AgentCore Identity M2M). One gateway, three targets.
if COMMUNITY_GATEWAY_URL and COMMUNITY_OAUTH_PROVIDER:
    register_tool_group(
        name="community",
        connect=lambda: MCPClient(
            lambda: create_streamable_http_transport_agentcore_identity(
                mcp_url=COMMUNITY_GATEWAY_URL,
                provider_name=COMMUNITY_OAUTH_PROVIDER,
                scopes=["community/read"],
            )
        ),
        resource_ids=[
            "Surplus-Listings",
            "Resource-Catalog",
            "Recipient-Needs",
        ],
    )
    system_prompt = system_prompt + """
- **Surplus donation listings**:
   - Retrieve surplus food and goods that donor organizations have posted as available
   - Do not return surplus listings from any other source

- **Community resource catalog**:
   - Retrieve the categories of food and goods circulating in the community network
   - Do not return catalog information other than from this tool

- **Recipient needs and requests**:
   - Retrieve what food banks, shelters, and partner organizations are currently requesting
   - Match available surplus to these needs, using only quantities and locations the tools return
   - Do not return recipient needs other than from this tool
"""
    logger.info("Community tools registered (AgentCore Identity M2M)")

# Pantry / stock levels at partner organizations (AgentCore Identity M2M).
if PANTRY_GATEWAY_URL and PANTRY_OAUTH_PROVIDER:
    register_tool_group(
        name="pantry",
        connect=lambda: MCPClient(
            lambda: create_streamable_http_transport_agentcore_identity(
                mcp_url=PANTRY_GATEWAY_URL,
                provider_name=PANTRY_OAUTH_PROVIDER,
                scopes=["pantry/read"],
            )
        ),
        resource_ids=["Pantry-Levels"],
    )
    system_prompt = system_prompt + """
- **Pantry and stock levels**:
   - Retrieve current stock levels at partner food banks and pantries
   - Use these levels to identify shortages and prioritize where surplus should go
   - Do not return stock levels other than from this tool
"""
    logger.info("Pantry tool registered (AgentCore Identity M2M)")

# Volunteers & vehicles for pickup/delivery routing (AgentCore Identity M2M).
if LOGISTICS_GATEWAY_URL and LOGISTICS_OAUTH_PROVIDER:
    register_tool_group(
        name="logistics",
        connect=lambda: MCPClient(
            lambda: create_streamable_http_transport_agentcore_identity(
                mcp_url=LOGISTICS_GATEWAY_URL,
                provider_name=LOGISTICS_OAUTH_PROVIDER,
                scopes=["logistics/read"],
            )
        ),
        resource_ids=[
            "Volunteers",
            "Vehicles",
        ],
    )
    system_prompt = system_prompt + """
- **Volunteers and vehicles (pickup & delivery)**:
   - Retrieve available volunteer drivers and vehicles, including their location and capacity
   - Suggest who could move a specific donation, using only the availability, location, and capacity the tools return
   - Do not return volunteer or vehicle information other than from these tools
"""
    logger.info("Logistics tools registered (AgentCore Identity M2M)")


def good_neighbor_agent(payload, context):
    """
    Invoke the agent with a payload using the Strands Agent framework.

    Tools are connected, AVP-filtered, and loaded per request inside an
    ExitStack so each MCP connection stays open for the duration of the agent
    call and is cleanly closed afterwards.
    """
    try:
        # Extract the user's input from the payload
        user_input = payload.get("prompt")
        print("User input:" + str(user_input))

        with ExitStack() as stack:
            session_tools = build_session_tools(context, stack)
            agent = Agent(
                model=model,
                system_prompt=system_prompt,
                tools=session_tools,
            )
            # The agent runs inside the ExitStack so MCP tool calls happen while
            # their connections are still open.
            response = agent(user_input)
            return response.message["content"][0]["text"]

    except Exception as e:
        print(f"Error invoking agent: {str(e)}")
        return f"I encountered an error while processing your request: {str(e)}"


@app.entrypoint
def invoke(payload, context):
    """Process user input and return a response using the Strands Agent"""
    try:
        response_text = good_neighbor_agent(payload, context)

        # Return response in the expected format
        return {
            "output": {
                "text": response_text
            },
            "metadata": {
                "prompt": payload.get("prompt", "Hello"),
                "agent": "good_neighbor_agent",
                "model": MODEL_ID,
                "authentication": "cognito_jwt"
            }
        }

    except Exception as e:
        # Return error in a safe format
        error_message = f"Error processing request: {str(e)}"
        print(error_message)
        return {
            "output": {
                "text": error_message
            },
            "error": str(e)
        }


if __name__ == "__main__":
    app.run()
