import { PublicApi, spec as PrivateAgentSpec } from '@sema4ai/agent-server-interface';
import { type MakeHttp, buildSpec } from './openapi.js';

export type PrivateAPIRoute = MakeHttp<(typeof PrivateAgentSpec)['paths']>;
export const parsePrivateApiRequest = buildSpec(PrivateAgentSpec);

export type PublicAPIRoute = MakeHttp<(typeof PublicApi.spec)['paths']>;
export const parsePublicApiRequest = buildSpec(PublicApi.spec);
