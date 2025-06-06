import { spec as apiSpec } from './spec.gen';

// In FastAPI, WebSocket routes are intentionally excluded from the OpenAPI (Swagger) spec.
// This is by design because OpenAPI (v3.0) does not officially support WebSocket endpoints
// in the same way it supports REST endpoints.
const wsSpec = {
  paths: {
    '/api/v2/runs/{aid}/stream': {
      get: {
        summary: 'Stream',
        operationId: 'run_stream_get',
        parameters: [
          {
            name: 'aid',
            in: 'path',
            required: true,
            schema: {
              type: 'string',
              title: 'Aid',
            },
          },
        ],
        responses: {
          '200': {
            description: 'Successful Response',
          },
        },
      },
    },
  },
} as const;

export const spec = {
  ...apiSpec,
  paths: {
    ...apiSpec.paths,
    ...wsSpec.paths,
  },
};
