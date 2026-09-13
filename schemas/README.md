# API and Lambda Function Schemas

This directory contains the OpenAPI specifications and Lambda function schema
used by the **Good Neighbor Agent** — a community waste-recovery assistant.

## Overview

These schemas are designed for use with **AgentCore Gateway** so the agent can
interact with the community recovery network — surplus listings, the shared
resource catalog, recipient needs, pantry stock levels, and volunteer/vehicle
logistics — through structured, validated interfaces.

## Schema Files

### OpenAPI Specifications (API Gateway Endpoints)

| File | Endpoint | Description |
|------|----------|-------------|
| `view-surplus-listings-api.json` | `GET /` | Surplus food and goods posted by donor organizations |
| `view-resource-catalog-api.json` | `GET /` | Community resource catalog with category/name filtering |
| `get-recipient-needs-api.json` | `GET /needs` | What food banks, shelters, and partners are requesting |
| `get-pantry-levels-api.json` | `GET /pantry` | Current stock levels at partner pantries |
| `get-volunteer-api.json` | `GET /volunteers` | Volunteer driver information |
| `get-vehicle-api.json` | `GET /vehicles` | Vehicle information for pickups and deliveries |

### Lambda Function Schema

| File | Function | Description |
|------|----------|-------------|
| `get-guidelines-lambda.json` | `get-guidelines` | Donation & food-safety guideline lookup (Acceptance / Window / Handling) |

## How the schemas map to the agent's tool groups

The agent (`static/AgentCode/agent.py`) registers its tools in groups. Each
gateway target's name prefix is also an Amazon Verified Permissions resource id,
so access can be filtered per requesting organization.

| Tool group | Inbound auth | Schemas |
|------------|--------------|---------|
| `guidelines` | AWS IAM (SigV4) | `get-guidelines-lambda.json` |
| `community` | OAuth2 via AgentCore Identity (M2M) | `view-surplus-listings-api.json`, `view-resource-catalog-api.json`, `get-recipient-needs-api.json` |
| `pantry` | OAuth2 via AgentCore Identity (M2M) | `get-pantry-levels-api.json` |
| `logistics` | OAuth2 via AgentCore Identity (M2M) | `get-volunteer-api.json`, `get-vehicle-api.json` |

## AgentCore Gateway Integration

Configure each gateway target with the matching schema. For API Gateway targets,
provide the OpenAPI file; for the guidelines Lambda target, provide the Lambda
schema.

The Lambda schema provides detailed input/output specifications for Model
Context Protocol (MCP) tool development:

1. **Input Validation** — request parameters with required fields and data types
2. **Output Contracts** — response schemas for success and error cases
3. **Authorization Context** — OAuth2 scopes (`community/read`, `pantry/read`)
   documented on the protected endpoints

## API Usage Examples

### View Surplus Listings
```bash
curl https://api-gateway-url/ \
  -H "Authorization: Bearer {jwt-token}"
```

### View Resource Catalog
```bash
# All resources
curl https://api-gateway-url/

# Filter by category
curl https://api-gateway-url/?category=produce

# Filter by resource name
curl https://api-gateway-url/?resource=Canned

# Combined filters
curl https://api-gateway-url/?category=produce&resource=Tomato
```

### Get Recipient Needs
```bash
# All current needs
curl https://api-gateway-url/needs

# Needs for a specific resource
curl https://api-gateway-url/needs?resource_id=RES001

# Needs for a specific organization
curl https://api-gateway-url/needs?org_id=ORG001
```

### Get Pantry Levels
```bash
# All pantry stock
curl https://api-gateway-url/pantry

# A specific resource
curl https://api-gateway-url/pantry?resource_id=RES001
```

### Get Volunteers
```bash
# All volunteers
curl https://api-gateway-url/volunteers

# Only available volunteers
curl https://api-gateway-url/volunteers?available=true

# A specific volunteer
curl https://api-gateway-url/volunteers/VOL001
```

### Get Vehicles
```bash
# All vehicles
curl https://api-gateway-url/vehicles

# Filter by capacity
curl https://api-gateway-url/vehicles?capacity=van

# A specific vehicle
curl https://api-gateway-url/vehicles/VEH001
```

## Schema Validation

All schemas follow these standards:
- **OpenAPI 3.0.3** for REST API specifications
- **JSON Schema Draft 7** for the Lambda function schema
- **Comprehensive Examples** for all request/response formats
- **Error Handling** specifications for all failure cases

## Security Considerations

1. **No Sensitive Data**: Schemas contain only structural information, no credentials
2. **Scoped Access**: Protected endpoints document their OAuth2 scopes
3. **Privacy**: Volunteer and recipient contact details are exposed only as
   needed to complete a pickup or delivery
4. **Authorization Patterns**: Gateway target prefixes double as AVP resource
   ids for per-organization access control

## Learning / design goals

These schemas support the agent's core goals:
- **Waste reduction**: get usable surplus to people quickly and safely
- **Community-scale service**: serve many organizations, not one customer
- **Delegated authorization**: role-based access (donor / recipient / coordinator)
- **Secure MCP integration**: structured tool interfaces for the AI agent

## Troubleshooting

### AgentCore Integration Issues
1. Verify each gateway target points at the correct schema file
2. Validate schema format using an online JSON Schema / OpenAPI validator
3. Check CloudWatch logs for Lambda or gateway errors

### API Testing Issues
1. Replace `{api-gateway-url}` with actual API Gateway endpoints
2. Ensure a valid JWT is supplied for protected endpoints
3. Confirm the OAuth2 scope matches the endpoint (`community/read`, `pantry/read`)

For additional setup, see the root [`README.md`](../README.md).
