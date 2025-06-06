import createClient, { ClientOptions } from 'openapi-fetch';

import type { paths } from './schema.gen';

type RequireSome<T, K extends keyof T> = Required<Pick<T, K>> & Omit<T, K>;

export const createAgentPublicApiSDK = (
  options: RequireSome<ClientOptions, 'baseUrl'>
) => createClient<paths>(options);
