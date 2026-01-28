# Plan: Prebuilt Tools Gallery

## Executive Summary

This plan outlines how to build a gallery of prebuilt tools for the SPAR platform, transitioning from the current custom action-based gallery to a hybrid approach leveraging vendor-provided remote MCPs and third-party integration platforms where beneficial.

---

## Current State Analysis

### MCP Support in SPAR (moonraker)

The platform already has comprehensive MCP infrastructure:

| Capability              | Status                                          |
| ----------------------- | ----------------------------------------------- |
| MCP Server Registration | API + file-based + embedded in agent specs      |
| Transports              | streamable-http, SSE, stdio                     |
| Hosted Deployments      | MCP Runtime service                             |
| OAuth2 Support          | Client credentials + authorization code flows   |
| Variable Types          | Strings, Secrets, OAuth2Secrets, DataServerInfo |
| Frontend UI             | Full CRUD for MCP servers                       |

Key files:

- Backend API: `server/src/agent_platform/server/api/private_v2/mcp_servers.py`
- Frontend: `workroom/spar-ui/src/components/MCPServers/`
- MCP Runtime: `workroom/mcp-runtime/`

### Existing Gallery (~/code/gallery/actions)

**44+ action packages** covering:

| Category         | Actions                                                | Auth Type         |
| ---------------- | ------------------------------------------------------ | ----------------- |
| Google Workspace | Calendar, Docs, Drive, Mail, Sheets (5)                | OAuth2            |
| Microsoft 365    | Calendar, Excel, Mail, OneDrive, SharePoint, Teams (6) | OAuth2            |
| CRM              | Salesforce, HubSpot, Zendesk, Linear, ServiceNow (5)   | OAuth2/API Key    |
| Data Warehouse   | Snowflake suite (6)                                    | Snowflake Secrets |
| Communication    | Slack, Email, Zoom (3)                                 | OAuth2/SMTP       |
| Documents        | PDF, Excel, Document Intelligence (5)                  | None              |
| Search           | Google Search, Perplexity, Serper (3)                  | API Key           |
| Web              | Browsing, AI-Browsing, Wayback, YouTube (4)            | None/API Key      |

---

## Third-Party Platform Analysis

### Composio (Primary Candidate)

**Pros:**

- 850+ toolkits, 11,000+ tools
- Full MCP server support with managed authentication
- Pre-built OAuth clients for 500+ apps (speeds development/prototyping)
- White-label UI customization (branding, colors, redirect URIs)
- SOC 2 compliant, automated token lifecycle
- User isolation built-in

**Cons:**

- Microsoft coverage appears limited (Outlook + Teams only; no explicit OneDrive, SharePoint, Excel support)
- Full white-labeling (removing Composio domain from OAuth consent screens) requires custom OAuth apps
- "Recommended for production" approach still requires creating your own OAuth apps
- Plan-based tool access restrictions

**Critical Gap:** Your requirement for "public and verified OAuth clients for ALL Google and Microsoft tools without users creating custom OAuth apps" is NOT fully met. Composio's pre-built OAuth is for prototyping; production use recommends custom apps.

### Alternative Platforms

| Platform       | MCP Support   | White-Label      | Managed OAuth    | Notes                            |
| -------------- | ------------- | ---------------- | ---------------- | -------------------------------- |
| **Paragon**    | ActionKit MCP | Yes (branded UI) | Yes              | Pro-code + visual builder        |
| **Merge**      | Agent Handler | Yes (Merge Link) | Yes              | Enterprise governance focus      |
| **Arcade.dev** | Yes           | Limited          | Yes              | Clean SDK, multiple auth methods |
| **Nango**      | Limited       | Yes              | Yes (paid tiers) | Open-source option available     |

**Reality Check:** No platform currently offers fully managed, public OAuth clients for the full depth of Google AND Microsoft APIs without any configuration. OAuth consent screens are controlled by Google/Microsoft, not integration platforms.

---

## Recommended Architecture

### Hybrid Approach: Three Tiers of Tools

```
┌─────────────────────────────────────────────────────────────────┐
│                        SPAR Tool Gallery                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │   Tier 1: BYOC   │  │  Tier 2: Managed │  │ Tier 3: Native │ │
│  │  (Bring Your Own │  │   (Platform-     │  │   (SPAR-owned  │ │
│  │   Credentials)   │  │    provided)     │  │    actions)    │ │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬────────┘ │
│           │                     │                     │          │
│  ┌────────▼─────────┐  ┌────────▼─────────┐  ┌───────▼────────┐ │
│  │ Vendor MCPs      │  │ Composio-backed  │  │ Hosted Action  │ │
│  │ - Google (OAuth) │  │ MCPs             │  │ Servers        │ │
│  │ - Microsoft      │  │ - Simple APIs    │  │ - PDF, Excel   │ │
│  │   (OAuth)        │  │ - Low-stakes     │  │ - Browsing     │ │
│  │ - Slack (OAuth)  │  │   integrations   │  │ - Custom logic │ │
│  └──────────────────┘  └──────────────────┘  └────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Tier Definitions

#### Tier 1: BYOC (Bring Your Own Credentials)

**For:** Google Workspace, Microsoft 365, Enterprise CRMs

Users/organizations configure their own OAuth apps once, then all users in their org can authenticate.

**Why this approach:**

- Google and Microsoft require OAuth apps to be in their respective marketplaces for "just click and go" public access
- Getting apps verified/published is a lengthy process with strict requirements
- Enterprise customers often WANT to use their own OAuth apps for security/compliance
- Provides deepest integration (full API access, custom scopes)

**User Experience:**

1. Org admin creates OAuth app in Google Cloud Console / Azure AD (one-time)
2. Admin configures credentials in SPAR tenant settings
3. End users click "Connect Google" → redirected to Google → authorize → done
4. No Composio/third-party branding in the flow

#### Tier 2: Managed (Platform-Provided)

**For:** Simple integrations, prototyping, non-sensitive tools

Use Composio or similar platform for tools where:

- Users expect quick setup
- Data sensitivity is lower
- Full enterprise control isn't required

**Examples:** Weather APIs, public data sources, simple webhooks, utilities

**User Experience:**

1. User selects tool from gallery
2. Clicks "Connect" → sees branded auth UI (can be white-labeled)
3. Authorizes via OAuth popup
4. Tool ready to use

#### Tier 3: Native (SPAR-Owned)

**For:** Local processing, no-auth tools, proprietary actions

Continue using the existing action server pattern for:

- Document processing (PDF, Excel)
- Browser automation
- Custom business logic
- Data transformations

**User Experience:**

1. Tool is available immediately (no auth needed)
2. Or: User provides file/data directly to agent

---

## User Experience Design

### Gallery Interface

```
┌─────────────────────────────────────────────────────────────────┐
│  🔧 Tool Gallery                                    [Search...] │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Categories: [All] [Productivity] [CRM] [Data] [Utilities]      │
│                                                                  │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │ 📧 Gmail        │ │ 📅 Google Cal   │ │ 📁 Google Drive │   │
│  │ ────────────────│ │ ────────────────│ │ ────────────────│   │
│  │ Send, search,   │ │ Create events,  │ │ Upload, search, │   │
│  │ manage email    │ │ check schedule  │ │ share files     │   │
│  │                 │ │                 │ │                 │   │
│  │ [Setup Required]│ │ [Setup Required]│ │ [Setup Required]│   │
│  │ [Add to Agent]  │ │ [Add to Agent]  │ │ [Add to Agent]  │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
│                                                                  │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │ 📄 PDF Tools    │ │ 📊 Excel        │ │ 🌐 Web Browse   │   │
│  │ ────────────────│ │ ────────────────│ │ ────────────────│   │
│  │ Extract text,   │ │ Read & write    │ │ Navigate pages, │   │
│  │ analyze PDFs    │ │ spreadsheets    │ │ extract data    │   │
│  │                 │ │                 │ │                 │   │
│  │ [Ready to Use]  │ │ [Ready to Use]  │ │ [Ready to Use]  │   │
│  │ [Add to Agent]  │ │ [Add to Agent]  │ │ [Add to Agent]  │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration Flow by Tier

#### Tier 1 (Google/Microsoft) - Admin Setup

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚙️ Configure Google Workspace Integration                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  To enable Google tools for your organization:                   │
│                                                                  │
│  1. Create OAuth credentials in Google Cloud Console             │
│     [📖 View Setup Guide]                                        │
│                                                                  │
│  2. Enter your credentials below:                                │
│                                                                  │
│     Client ID:     [_________________________________]           │
│     Client Secret: [_________________________________]           │
│                                                                  │
│  3. Configure redirect URI in Google Console:                    │
│     https://your-spar-instance.com/oauth/callback/google         │
│                                                                  │
│  4. Select scopes to enable:                                     │
│     ☑️ Gmail (read, send, manage)                                │
│     ☑️ Calendar (read, write)                                    │
│     ☑️ Drive (read, write)                                       │
│     ☑️ Sheets (read, write)                                      │
│     ☑️ Docs (read, write)                                        │
│                                                                  │
│  [Test Connection]                    [Save Configuration]       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Tier 1 - End User Auth (after admin setup)

```
┌─────────────────────────────────────────────────────────────────┐
│  Connect Your Google Account                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Your agent needs access to Google services.                     │
│                                                                  │
│  Requested permissions:                                          │
│  • Read and send email                                          │
│  • Manage calendar events                                        │
│  • Access Google Drive files                                     │
│                                                                  │
│           [🔵 Sign in with Google]                               │
│                                                                  │
│  Your credentials are stored securely and can be                 │
│  revoked at any time from your account settings.                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Integration Architecture

### MCP Server Registry

```yaml
# Example: Gallery tool definition
tools:
  google-gmail:
    display_name: 'Gmail'
    description: 'Send, search, and manage email'
    category: 'productivity'
    tier: 'byoc'
    auth_type: 'oauth2'
    provider: 'google'
    required_scopes:
      - 'https://www.googleapis.com/auth/gmail.modify'
      - 'https://www.googleapis.com/auth/gmail.send'
    mcp_source:
      type: 'vendor' # or "composio" or "native"
      # For vendor MCP:
      url_template: 'https://mcp.googleapis.com/gmail/v1'
      # For Composio:
      toolkit_id: 'gmail'
      # For native:
      action_package: '@gallery/google-mail'

  pdf-tools:
    display_name: 'PDF Tools'
    description: 'Extract and analyze PDF documents'
    category: 'utilities'
    tier: 'native'
    auth_type: 'none'
    mcp_source:
      type: 'native'
      action_package: '@gallery/pdf'
```

### OAuth Credential Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Admin   │     │   SPAR   │     │  Google/ │     │   User   │
│  Setup   │     │  Backend │     │Microsoft │     │   Auth   │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ 1. Configure   │                │                │
     │    OAuth App   │                │                │
     │───────────────>│                │                │
     │                │                │                │
     │ 2. Store       │                │                │
     │    encrypted   │                │                │
     │    credentials │                │                │
     │                │                │                │
     │                │                │                │
     │                │                │    3. User     │
     │                │                │    connects    │
     │                │<───────────────────────────────│
     │                │                │                │
     │                │ 4. Redirect to │                │
     │                │    provider    │                │
     │                │───────────────>│                │
     │                │                │                │
     │                │                │ 5. User        │
     │                │                │    authorizes  │
     │                │                │<───────────────│
     │                │                │                │
     │                │ 6. Token       │                │
     │                │    exchange    │                │
     │                │<───────────────│                │
     │                │                │                │
     │                │ 7. Store user  │                │
     │                │    tokens      │                │
     │                │    (encrypted) │                │
     │                │                │                │
```

### Database Schema Addition

```sql
-- New table for gallery tool definitions
CREATE TABLE v2.gallery_tool (
    tool_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('byoc', 'managed', 'native')),
    auth_type TEXT NOT NULL,
    provider TEXT,
    required_scopes JSONB,
    mcp_source JSONB NOT NULL,
    icon_url TEXT,
    documentation_url TEXT,
    is_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Tenant-level OAuth app configurations (Tier 1)
CREATE TABLE v2.tenant_oauth_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES v2.tenant(tenant_id),
    provider TEXT NOT NULL,  -- 'google', 'microsoft', etc.
    client_id_enc TEXT NOT NULL,  -- encrypted
    client_secret_enc TEXT NOT NULL,  -- encrypted
    redirect_uri TEXT NOT NULL,
    enabled_scopes JSONB,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, provider)
);

-- User-level OAuth tokens
CREATE TABLE v2.user_oauth_token (
    token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    provider TEXT NOT NULL,
    access_token_enc TEXT NOT NULL,  -- encrypted
    refresh_token_enc TEXT,  -- encrypted
    token_expiry TIMESTAMPTZ,
    granted_scopes JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, tenant_id, provider)
);
```

---

## Migration Path

### Phase 1: Gallery Infrastructure (Foundation)

- Build gallery UI in frontend
- Create gallery tool registry (database + API)
- Implement tool discovery endpoint
- Add tenant OAuth configuration UI

### Phase 2: Tier 1 - Google & Microsoft

- Implement OAuth app configuration flow for admins
- Build user OAuth connection flow
- Create MCP server adapters for Google APIs
- Create MCP server adapters for Microsoft Graph API
- Migrate existing gallery actions to MCP format

### Phase 3: Tier 2 - Managed Tools (Optional)

- Evaluate Composio integration for non-core tools
- Implement Composio MCP proxy if valuable
- White-label configuration

### Phase 4: Tier 3 - Native Tools

- Migrate existing action packages to gallery
- Standardize action package → MCP server conversion
- Build "instant deploy" from gallery to MCP Runtime

---

## Configuration Requirements Summary

### For Org Admins (One-Time Setup)

| Integration      | Requirement                                                 |
| ---------------- | ----------------------------------------------------------- |
| Google Workspace | Create OAuth app in Google Cloud Console, configure in SPAR |
| Microsoft 365    | Create app registration in Azure AD, configure in SPAR      |
| Salesforce       | Create Connected App, configure in SPAR                     |
| Slack            | Create Slack App, configure in SPAR                         |

### For End Users

| Tool Tier        | User Action Required                                 |
| ---------------- | ---------------------------------------------------- |
| Tier 1 (BYOC)    | Click "Connect" → Authorize in provider popup → Done |
| Tier 2 (Managed) | Click "Connect" → Authorize in provider popup → Done |
| Tier 3 (Native)  | None - tools ready immediately                       |

---

## Open Questions for Decision

1. **Composio Integration Depth**

   - Option A: Use Composio for ALL OAuth management (simplest, but less control)
   - Option B: Use Composio only for Tier 2 tools (balanced)
   - Option C: Build all OAuth handling natively (most control, most work)
   - **Recommendation:** Option B

2. **Google/Microsoft OAuth App Strategy**

   - Option A: Provide pre-configured Sema4.ai OAuth apps (users see Sema4.ai brand)
   - Option B: Require each tenant to create their own apps (full white-label)
   - Option C: Offer both (Sema4.ai apps for quick start, BYOC for enterprise)
   - **Recommendation:** Option C

3. **Gallery Packaging**

   - Option A: Ship tools as part of SPAR (always available)
   - Option B: Tools as installable marketplace items
   - Option C: Mix - core tools built-in, extended tools in marketplace
   - **Recommendation:** Option C

4. **Vendor MCP vs Custom Implementation**
   - Google and Microsoft are rapidly releasing official MCP servers
   - Should we use vendor MCPs when available vs our own implementations?
   - **Recommendation:** Prefer vendor MCPs, fall back to custom

---

## Sources & References

- [Composio Managed Authentication](https://docs.composio.dev/docs/managed-authentication)
- [Composio Custom Auth Configs (White-labeling)](https://docs.composio.dev/docs/custom-auth-configs)
- [Composio MCP Quickstart](https://docs.composio.dev/docs/mcp-quickstart)
- [OAuth 2.1 in MCP](https://composio.dev/blog/oauth-2-1-in-mcp)
- [AI Agent Authentication Platforms Comparison](https://composio.dev/blog/ai-agent-authentication-platforms)
- [Best MCP Gateways for Developers](https://composio.dev/blog/best-mcp-gateway-for-developers)
- [Merge Agent Handler](https://www.merge.dev/blog/best-ai-agent-auth-tool)
- [Nango Alternatives](https://composio.dev/blog/nango-alternatives-ai-agents)
