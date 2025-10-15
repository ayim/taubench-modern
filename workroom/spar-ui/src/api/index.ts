import { paths as AgentServerPaths } from '@sema4ai/agent-server-interface';
import { OAuthProvider } from '@sema4ai/oauth-client';

import type { OpenAPIClient } from './OpenAPIClient';
import type { SparUIRoutes, LooseRouteParams } from './routes';
import { AgentOAuthProviderState } from '../lib/OAuth';
import { ActionPackage } from '../lib/DeprecatedTypes';

type ApiResponse<Success> = { data: Success; success: true } | { success: false; error: { message: string } };

export enum SparUIFeatureFlag {
  showActionLogs = 'showActionLogs',
  showFeedback = 'showFeedback',
  canEditAgent = "canEditAgent",
  deploymentWizard = 'deploymentWizard',
  agentDetails = 'agentDetails',
}

export type NavigationArgs = {
  [K in keyof SparUIRoutes]: { to: K; params: SparUIRoutes[K] };
}[keyof SparUIRoutes];

export interface SparAPIClient {
  /**
   * Request for enabled feature at target application
   */
  getFeatureFlag: (feature: SparUIFeatureFlag) => boolean;

  /**
   * Agent Server API client
   */
  queryAgentServer: OpenAPIClient<AgentServerPaths>;

  /**
   * Start a websocket stream for a given thread
   */
  startWebsocketStream: (agentId: string) => Promise<WebSocket>;

  /**
   * Get the HTML for the action log
   */
  openActionLogs: (props: {
    agentId: string;
    threadId: string;
    toolCallId: string;
    // Only surfaced by agent-server >= 2.1.6
    actionServerRunId: string | null;
  }) => Promise<{ success: true } | { success: false; error: { message: string } }>;

  /**
   * Download a file
   */
  downloadFile: (props: { threadId: string; name: string }) => Promise<void>;

  /**
   * Navigation helper
   */
  navigate: (args: NavigationArgs) => void;

  /**
   * Get Agent OAuth provider state
   */
  getAgentOAuthState: (props: { agentId: string }) => Promise<AgentOAuthProviderState[]>;

  /**
   * Initiate OAuth authorization flow
   */
  authorizeAgentOAuth: (props: { agentId: string; provider: OAuthProvider; uri: string }) => Promise<void>;

  /**
   * Delete active OAuth provider connection
   */
  deleteAgentOAuth: (props: { agentId: string; provider: OAuthProvider; connectionId: string }) => Promise<void>;
  /**
   * Returns required params for a given route
   */
  useParamsFn: {
    (route: { strict: false }): LooseRouteParams;
    <T extends keyof SparUIRoutes>(route: T): SparUIRoutes[T];
  };

  /**
   * Get route path for a given route and params
   */
  useRouteFn: <T extends keyof SparUIRoutes>(
    route: T,
    params: SparUIRoutes[T],
  ) => {
    href: string;
    current: boolean;
  };

  /**
   * Retrieve the URL for the Work Item API
   */
  getWorkItemAPIURL: () => Promise<ApiResponse<string>>;

  /**
   * Send feedback
   */
  sendFeedback?: (props: { agentId: string; threadId: string; feedback: string; comment: string }) => Promise<boolean>;

  /**
   * @deprecated Do not use
   * Used to get Action details for a given agent including OAuth information
   * TODO: In future, this information should be returned by Agent Server
   */
  getActionDetails?: (props: { agentId: string }) => Promise<ActionPackage[]>;
}
