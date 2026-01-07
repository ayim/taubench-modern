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
