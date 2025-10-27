# Semantic Data Model Export/Import API

This document describes the new API endpoints for exporting and importing semantic data models (SDMs) in a portable format.

## Overview

The export/import API endpoints allow you to:

1. **Export** an SDM from one environment with data connection names (portable)
2. **Import** the SDM into another environment where connection names are resolved to IDs

This is useful for:

- Moving SDMs between development, staging, and production environments
- Sharing SDMs across different workspaces
- Backing up and restoring SDM configurations

## How It Works

**Export:** Replaces environment-specific `data_connection_id` (UUID) with portable `data_connection_name` in YAML format.

**Import:** Resolves `data_connection_name` back to `data_connection_id` in target environment (case-insensitive matching).

**Key Rules:**

- ⚠️ All data connections **must exist** in target environment before import (or import fails with HTTP 400)
- 🔄 Automatic deduplication when `agent_id` is provided (prevents duplicate SDMs)
- ✅ New SDM ID is generated (unless duplicate found)

---

## Prerequisites

**Before Importing (Critical):**

- ⚠️ All data connections referenced in the YAML **must already exist** in the target environment
- ✅ Connection names should match (case-insensitive) or edit the YAML to use existing connection names
- ✅ User must have permission to create semantic data models

> **Note:** Import will fail with HTTP 400 if any connection is missing. Create connections first!

---

## API Endpoints

### 1. Export Semantic Data Model

**Endpoint:** `GET /api/v2/semantic-data-models/{semantic_data_model_id}/export`

**Description:** Export an SDM as a YAML file with `data_connection_name` instead of `data_connection_id`.

**Request:**

```bash
curl -X GET "https://api.example.com/api/v2/semantic-data-models/{sdm-id}/export" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o customer-model.yaml
```

**Response:** YAML file with `Content-Type: application/x-yaml`

```yaml
name: Customer Analytics Model
description: Analytics for customer data
tables:
  - name: customers
    base_table:
      data_connection_name: Production Database # ← Name, not ID!
      database: PROD_DB
      table: CUSTOMERS
    # ... dimensions, measures, etc.
```

**Key Points:**

- ❌ `semantic_data_model_id` is NOT included (for portability)
- ✅ `data_connection_id` replaced with `data_connection_name`
- 📄 YAML format (matches Snowflake Cortex Analyst spec)

---

### 2. Import Semantic Data Model

**Endpoint:** `POST /api/v2/semantic-data-models/import`

**Description:** Import an SDM from a portable format, resolving `data_connection_name` to `data_connection_id`.

**Request:**

```bash
curl -X POST "https://api.example.com/api/v2/semantic-data-models/import" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "semantic_model": { /* SDM with data_connection_name */ },
    "agent_id": "agent-uuid-optional"  // Optional: enables deduplication
  }'
```

**Parameters:**

- `semantic_model` (required): SDM object with `data_connection_name` instead of `data_connection_id`
- `agent_id` (optional): Enables deduplication for this agent

**Success Response (New SDM):**

```json
{
  "semantic_data_model_id": "new-uuid-456",
  "resolved_data_connections": {
    "Production Database": "data-connection-uuid-789"
  },
  "is_duplicate": false,
  "warnings": []
}
```

**Success Response (Duplicate Found):**

```json
{
  "semantic_data_model_id": "existing-uuid-123",
  "resolved_data_connections": {
    "Production Database": "data-connection-uuid-789"
  },
  "is_duplicate": true,
  "warnings": []
}
```

**Error Response (Unresolved Connections - HTTP 400):**

```json
{
  "error": {
    "code": "bad_request",
    "message": "Cannot import SDM: 1 data connection(s) not found:\n  - Analytics Database\n\nPlease create these data connections in the target environment before importing.\nAvailable connections: Production Database, Staging Database"
  }
}
```

**Notes:**

- Connection names are resolved **case-insensitively**
- **Deduplication**: If `agent_id` is provided and a matching SDM exists (same name + content), the existing SDM ID is returned with `is_duplicate: true`
- **Validation**: If connections can't be resolved, the import **fails** with HTTP 400 and lists available connections
- You can link the SDM to agents/threads using the returned `semantic_data_model_id`

---

## Deduplication

When `agent_id` is provided during import, the system checks for existing SDMs with matching name and content structure.

**Behavior:**

- ✅ **Match found:** Returns existing SDM ID with `is_duplicate: true`
- 🆕 **No match:** Creates new SDM with `is_duplicate: false`

**Matching criteria:** Same name (case-insensitive) + same structure (ignoring connection IDs/names)

**Without `agent_id`:** Deduplication is disabled, always creates new SDM.

---

## Quick Start: Moving SDM Between Environments

**1. Export from source:**

```bash
curl -X GET "https://source-api.example.com/api/v2/semantic-data-models/{sdm-id}/export" \
  -H "Authorization: Bearer SOURCE_TOKEN" \
  -o my-sdm.yaml
```

**2. Review the YAML** (optional - edit connection names if needed)

**3. Import to target:**

```bash
# Read YAML and convert to JSON for the API call
curl -X POST "https://target-api.example.com/api/v2/semantic-data-models/import" \
  -H "Authorization: Bearer TARGET_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "semantic_model": <YAML_CONTENT_AS_JSON>,
    "agent_id": "target-agent-id"
  }'
```

**Note:** You'll need to convert the YAML to JSON format for the import API, or use a tool/script to automate this process.
