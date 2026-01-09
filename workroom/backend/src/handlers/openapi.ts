import { PublicApi } from '@sema4ai/agent-server-interface';
import { type ExpressRequest, type ExpressResponse } from '../interfaces.js';

type OpenApiSpec = typeof PublicApi.spec;
type OpenApiServerObject = { url: string; description?: string };

const PUBLIC_API_PATH_PREFIX = '/api/public/v1';

const rewritePaths = (paths: OpenApiSpec['paths']): OpenApiSpec['paths'] => {
  const rewrittenPaths: Record<string, (typeof paths)[keyof typeof paths]> = {};

  for (const [path, pathItem] of Object.entries(paths)) {
    const rewrittenPath = path.startsWith(PUBLIC_API_PATH_PREFIX) ? path.slice(PUBLIC_API_PATH_PREFIX.length) : path;
    rewrittenPaths[rewrittenPath] = pathItem;
  }

  return rewrittenPaths as OpenApiSpec['paths'];
};

const TITLE = 'Sema4.ai Team Edition API';
const API_KEYS_PATH = '/configuration/api-keys/new';

const buildDescription = ({ serverUrl }: { serverUrl: string }): string =>
  `Get your API key: ${serverUrl}${API_KEYS_PATH}`;

const SECURITY_SCHEMES = {
  BearerAuth: {
    type: 'http',
    scheme: 'bearer',
  },
} as const;

const buildOpenApiResponse = ({
  baseUrl,
  serverUrl,
  spec,
}: {
  baseUrl: string;
  serverUrl: string;
  spec: OpenApiSpec;
}) => {
  const { openapi, info: _info, paths, components, ...rest } = spec;
  const rewrittenPaths = rewritePaths(paths);

  return {
    openapi,
    info: { title: TITLE, description: buildDescription({ serverUrl }) },
    servers: [{ url: baseUrl }] as OpenApiServerObject[],
    paths: rewrittenPaths,
    components: {
      ...components,
      securitySchemes: SECURITY_SCHEMES,
    },
    ...rest,
  };
};

export const createPublicApiSpecHandler = () => (req: ExpressRequest, res: ExpressResponse) => {
  const protocol = req.header('x-forwarded-proto') ?? req.protocol;
  const host = req.header('x-forwarded-host') ?? req.get('host') ?? req.hostname;
  const tenantBaseUrl = `${protocol}://${host}${req.baseUrl}`;
  const apiBaseUrl = `${tenantBaseUrl}/api/v1`;

  const specWithServers = buildOpenApiResponse({
    baseUrl: apiBaseUrl,
    serverUrl: tenantBaseUrl,
    spec: PublicApi.spec,
  });

  res.json(specWithServers);
};
