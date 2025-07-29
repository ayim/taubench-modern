import { spec as AgentSpec } from '@sema4ai/agent-server-interface';
import { type MakeHttp, buildSpec } from './openapi.js';

export type AgentAPIRoute = MakeHttp<(typeof AgentSpec)['paths']>;
export const parseAgentRequest = buildSpec(AgentSpec);
