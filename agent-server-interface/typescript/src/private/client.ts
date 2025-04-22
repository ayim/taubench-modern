import createClient from 'openapi-fetch';

import type { paths } from './schema.gen';

export const createAgentSDK = ({ baseUrl }: { baseUrl: string }) =>
  createClient<paths>({ baseUrl });
