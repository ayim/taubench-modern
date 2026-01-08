## MCP Runtime API Endpoints

### Health & Readiness

| Method | Path          | Description                                                                                             |
| ------ | ------------- | ------------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/health` | Health check. Always returns `200` with `{ status: 'ok' }`                                              |
| `GET`  | `/api/ready`  | Readiness check. Returns `200` when ready, `503` during application startup (Action Server rehydration) |

### Deployments

| Method   | Path                              | Description             |
| -------- | --------------------------------- | ----------------------- |
| `POST`   | `/api/deployments/{deploymentId}` | Create a new deployment |
| `GET`    | `/api/deployments/{deploymentId}` | Get deployment by ID    |
| `GET`    | `/api/deployments`                | List all deployments    |
| `DELETE` | `/api/deployments/{deploymentId}` | Delete a deployment     |

### Action Server Proxy

| Method | Path                            | Description                                   |
| ------ | ------------------------------- | --------------------------------------------- |
| `*`    | `/deployments/{deploymentId}/*` | Proxy requests to the deployment Action Server |

---

### Endpoint Details

#### POST `/api/deployments/{deploymentId}`

- Content-Type: `application/octet-stream`
- Body: Agent package zip file (max 50MB)
- `deploymentId` must be a valid UUID
- **Returns:** `{ deploymentId, status, url }`

#### GET `/api/deployments/{deploymentId}`

- **Returns:** `{ deploymentId, status, url }` or `null` if not found

#### GET `/api/deployments`

- **Returns:** Array of `{ deploymentId, status, url }`

#### DELETE `/api/deployments/{deploymentId}`

- **Returns:** `{ deploymentId, deleted: true }` on success
- Returns error if deployment not found

#### `/deployments/{deploymentId}/*`

- Proxies all requests to the internal Action Server for the given deployment
- Example: `GET /deployments/abc-123/mcp/actions` → `GET http://localhost:20001/mcp/actions`
- Returns `404` if deployment not found
- Returns `502` on proxy errors

#### Errors

All endpoints may return error responses in the format:

```json
{
  "success": false,
  "error": {
    "code": "...",
    "message": "..."
  }
}
```
