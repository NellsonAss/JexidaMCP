# Patreon Integration Guide

This document describes how to set up and use the Patreon MCP tools in JexidaMCP.

## Overview

The Patreon integration provides MCP tools to:
- Get creator/campaign information
- List tiers and their details
- List and filter patrons
- Export patron data for automation workflows (email, Discord, etc.)

## Patreon API Setup Guide

### Step 1: Create a Patreon OAuth2 Application

1. Go to [Patreon Developer Portal](https://www.patreon.com/portal/registration/register-clients)
2. Log in with your creator account
3. Click "Create Client"
4. Fill in the application details:
   - **App Name**: JexidaMCP Integration
   - **Description**: MCP automation for patron management
   - **App Category**: Tool
   - **Redirect URIs**: `http://localhost:8080/patreon/callback` (for initial setup)
   - **Client API Version**: 2
5. Click "Create Client"
6. Note down your **Client ID** and **Client Secret**

### Step 2: Get Your Creator Access Token (Quick Setup)

For quick setup, you can use the Creator's Access Token from the Patreon developer portal:

1. In the developer portal, find your created client
2. Click on the client to view details
3. Look for "Creator's Access Token" section
4. Click "Create" to generate a new token
5. **Copy this token immediately** - it won't be shown again

This token is tied to your creator account and has full access to your campaign data.

### Step 3: Get OAuth2 Tokens (Production Setup)

For production use with token refresh capability:

#### 3a. Generate Authorization URL

Build an authorization URL with these parameters:

```
https://www.patreon.com/oauth2/authorize?
  response_type=code&
  client_id=YOUR_CLIENT_ID&
  redirect_uri=http://localhost:8080/patreon/callback&
  scope=identity identity[email] campaigns campaigns.members&
  state=random_state_string
```

Required scopes:
- `identity` - Access your identity
- `identity[email]` - Access your email
- `campaigns` - Access your campaigns
- `campaigns.members` - Access patron/member data

#### 3b. Exchange Authorization Code

After authorizing, you'll be redirected to your callback URL with a `code` parameter.

Exchange this code for tokens:

```bash
curl -X POST https://www.patreon.com/api/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "code=YOUR_AUTH_CODE" \
  -d "grant_type=authorization_code" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "redirect_uri=http://localhost:8080/patreon/callback"
```

Response:
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 2678400,
  "scope": "identity identity[email] campaigns campaigns.members",
  "token_type": "Bearer"
}
```

Save both `access_token` and `refresh_token`.

### Step 4: Find Your Campaign ID

Once you have an access token, find your campaign ID:

```bash
curl -X GET "https://www.patreon.com/api/oauth2/v2/campaigns" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response will include your campaign(s):
```json
{
  "data": [
    {
      "id": "12345678",
      "type": "campaign"
    }
  ]
}
```

Note down the campaign `id` for configuration.

## Environment Variables

### Quick Setup (Access Token Only)

Set these environment variables on the MCP server:

| Variable | Description | Required |
|----------|-------------|----------|
| `PATREON_ACCESS_TOKEN` | Creator access token | Yes |
| `PATREON_CREATOR_CAMPAIGN_ID` | Your campaign ID | Recommended |

Example `.env`:
```bash
PATREON_ACCESS_TOKEN=your_creator_access_token_here
PATREON_CREATOR_CAMPAIGN_ID=12345678
```

### Production Setup (OAuth2 with Refresh)

For automatic token refresh:

| Variable | Description | Required |
|----------|-------------|----------|
| `PATREON_CLIENT_ID` | OAuth2 client ID | Yes |
| `PATREON_CLIENT_SECRET` | OAuth2 client secret | Yes |
| `PATREON_ACCESS_TOKEN` | Current access token | Yes |
| `PATREON_REFRESH_TOKEN` | Refresh token | Yes |
| `PATREON_CREATOR_CAMPAIGN_ID` | Your campaign ID | Recommended |

Example `.env`:
```bash
PATREON_CLIENT_ID=your_client_id
PATREON_CLIENT_SECRET=your_client_secret
PATREON_ACCESS_TOKEN=your_access_token
PATREON_REFRESH_TOKEN=your_refresh_token
PATREON_CREATOR_CAMPAIGN_ID=12345678
```

### Using the Secrets Store

You can also store Patreon credentials in the encrypted secrets store:

```bash
# Via MCP API
curl -X POST http://192.168.1.224:8080/tools/api/tools/store_secret/run/ \
  -H "Content-Type: application/json" \
  -d '{
    "service_type": "patreon",
    "key": "access_token",
    "value": "your_token_here"
  }'
```

## Tool Reference

### patreon_get_creator

Get creator and primary campaign information.

**Input**: None

**Output**:
```json
{
  "success": true,
  "creator_id": "12345",
  "creator_name": "John Creator",
  "creator_email": "john@example.com",
  "campaign": {
    "id": "67890",
    "name": "My Awesome Project",
    "patron_count": 150,
    "url": "https://www.patreon.com/myproject",
    "summary": "...",
    "is_monthly": true
  }
}
```

**Example**:
```bash
curl -X POST http://192.168.1.224:8080/tools/api/tools/patreon_get_creator/run/ \
  -H "Content-Type: application/json" \
  -d '{}'
```

### patreon_get_tiers

List all tiers for a campaign.

**Input**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `campaign_id` | string | Optional. Uses env default if not provided |

**Output**:
```json
{
  "success": true,
  "campaign_id": "67890",
  "tiers": [
    {
      "id": "tier1",
      "title": "Supporter",
      "amount_cents": 500,
      "description": "Basic support tier",
      "patron_count": 100,
      "published": true
    },
    {
      "id": "tier2",
      "title": "Elder",
      "amount_cents": 2500,
      "description": "Premium tier with extra benefits",
      "patron_count": 25,
      "published": true
    }
  ],
  "count": 2
}
```

### patreon_get_patrons

List patrons with optional filtering.

**Input**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `campaign_id` | string | Optional. Uses env default if not provided |
| `status_filter` | string | Optional. Filter: `active_patron`, `declined_patron`, `former_patron` |
| `tier_filter` | string | Optional. Filter by tier name (case-insensitive partial match) |

**Output**:
```json
{
  "success": true,
  "campaign_id": "67890",
  "patrons": [
    {
      "id": "member1",
      "full_name": "Jane Patron",
      "email": "jane@example.com",
      "patron_status": "active_patron",
      "lifetime_support_cents": 15000,
      "currently_entitled_amount_cents": 500,
      "last_charge_date": "2024-01-01",
      "last_charge_status": "Paid",
      "pledge_start": "2023-06-15",
      "tier_id": "tier1",
      "tier_name": "Supporter"
    }
  ],
  "count": 150,
  "total_monthly_cents": 75000
}
```

**Example - Get Elder Tier Patrons**:
```bash
curl -X POST http://192.168.1.224:8080/tools/api/tools/patreon_get_patrons/run/ \
  -H "Content-Type: application/json" \
  -d '{"tier_filter": "Elder"}'
```

### patreon_get_patron

Get details for a specific patron.

**Input**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `patron_id` | string | Required. The member ID |

**Output**:
```json
{
  "success": true,
  "patron": {
    "id": "member1",
    "full_name": "Jane Patron",
    "email": "jane@example.com",
    "patron_status": "active_patron",
    "lifetime_support_cents": 15000,
    "currently_entitled_amount_cents": 500,
    "last_charge_date": "2024-01-01",
    "last_charge_status": "Paid",
    "pledge_start": "2023-06-15",
    "tier_id": "tier1",
    "tier_name": "Supporter"
  }
}
```

### patreon_export_patrons

Export patron data for external use.

**Input**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `campaign_id` | string | Optional. Uses env default if not provided |
| `status_filter` | string | Optional. Filter by status |
| `format` | string | `json` (default) or `csv` |

**Output**:
```json
{
  "success": true,
  "format": "csv",
  "data": "id,full_name,email,patron_status,...\nmember1,Jane Patron,jane@example.com,active_patron,...",
  "count": 150
}
```

**Example - Export Active Patrons as CSV**:
```bash
curl -X POST http://192.168.1.224:8080/tools/api/tools/patreon_export_patrons/run/ \
  -H "Content-Type: application/json" \
  -d '{"status_filter": "active_patron", "format": "csv"}'
```

## Integration Examples

### Export Patrons for Email Workflow

```bash
# Get active patrons as CSV for email marketing
curl -X POST http://192.168.1.224:8080/tools/api/tools/patreon_export_patrons/run/ \
  -H "Content-Type: application/json" \
  -d '{"status_filter": "active_patron", "format": "csv"}' \
  | jq -r '.data' > patrons.csv
```

### Filter by Elder Tier for Special Access

```bash
# Get patrons in "Elder" tier
curl -X POST http://192.168.1.224:8080/tools/api/tools/patreon_get_patrons/run/ \
  -H "Content-Type: application/json" \
  -d '{"tier_filter": "Elder"}'
```

### Combine with Discord Tools

Use patron emails to match Discord members:

```python
# Pseudo-code for n8n or custom automation
patrons = call_mcp_tool("patreon_get_patrons", {"tier_filter": "Elder"})
discord_members = call_mcp_tool("discord_get_members", {})

# Match and assign roles
for patron in patrons["patrons"]:
    for member in discord_members["members"]:
        if patron["email"] == member.get("email"):
            call_mcp_tool("discord_add_role", {
                "user_id": member["id"],
                "role_name": "Patreon Elder"
            })
```

## Troubleshooting

### "No Patreon credentials configured"

Ensure at least one of:
- `PATREON_ACCESS_TOKEN` is set, OR
- All of `PATREON_CLIENT_ID`, `PATREON_CLIENT_SECRET`, `PATREON_REFRESH_TOKEN` are set

### "Access token is invalid or expired"

If using quick setup:
- Generate a new Creator's Access Token from the Patreon developer portal

If using OAuth2:
- Ensure `PATREON_REFRESH_TOKEN` is set
- The integration will automatically refresh the token

### "No campaign_id provided"

Either:
- Set `PATREON_CREATOR_CAMPAIGN_ID` environment variable, OR
- Pass `campaign_id` parameter to each tool call

### Rate Limits

Patreon API has rate limits. If you see 429 errors:
- Add delays between bulk operations
- Use the export tool for large data pulls
- Cache results when possible

## Security Notes

- Never log or expose access tokens
- Store credentials in environment variables or the encrypted secrets store
- Use OAuth2 refresh flow for production to handle token expiration
- The integration never logs secret values

