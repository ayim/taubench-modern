import { paths as AgentServerPaths } from '@sema4ai/agent-server-interface';
import { OAuthProvider } from '@sema4ai/oauth-client';

import type { OpenAPIClient } from './OpenAPIClient';
import type { SparUIRoutes, LooseRouteParams } from './routes';
import { AgentOAuthProviderState } from '../lib/OAuth';
import { ActionPackage } from '../lib/DeprecatedTypes';

type ApiResponse<Success> = { data: Success; success: true } | { success: false; error: { message: string } };

export enum SparUIFeatureFlag {
  showActionLogs = 'showActionLogs',
  canCreateAgents = 'canCreateAgents',
  canConfigureAgents = 'canConfigureAgents',
  deploymentWizard = 'deploymentWizard',
  agentDetails = 'agentDetails',
  documentIntelligence = 'documentIntelligence',
  semanticDataModels = 'semanticDataModels',
  agentFeedback = 'agentFeedback',
  agentChatInput = 'agentChatInput',
  violetAgentChat = 'violetAgentChat',
}

export type NavigationArgs = {
  [K in keyof SparUIRoutes]: { to: K; params: SparUIRoutes[K]; search?: Record<string, unknown> };
}[keyof SparUIRoutes];

export type AnalyticsEvent =
  | `scenario_${string}.run_${string}.started`
  | `scenario_${string}.run_${string}.duration`
  | `scenario_${string}.run_${string}.selected`
  | `scenario_${string}.run_${string}.view_results`
  | `scenario_${string}.run_${string}.view_trial_details`
  | `scenario_${string}.run_${string}.view_evaluation`
  | `scenario_${string}.run_${string}.view_execution_thread`
  | `scenario_${string}.run_${string}.canceled`
  | `evals_panel.navigate_to_view`
  | `scenario_creation.started`
  | `scenario_creation.name_modified`
  | 'scenario_creation.description_modified'
  | 'scenario_creation.expectation_modified'
  | 'scenario_creation.saved'
  | 'scenario_creation.canceled'
  | `scenario_batch_run_${string}.started`
  | `scenario_batch_run_${string}.canceled`
  // agentName.type.dialect, e.g. "MyAgentName.file.xlsx" or "MyAgentName.database.redshift"
  | `semantic_data_model.created.${string}.${string}.${string}`
  | `semantic_data_model.imported.${string}.${string}.${string}`
  | `semantic_data_model.modified`
  | `semantic_data_model.deleted`
  | `semantic_data_model.verified_query.created.${string}.${string}.${string}`
  | `semantic_data_model.verified_query.modified`
  | `semantic_data_model.verified_query.deleted`;

export interface SparAPIClient {
  /**
   * Request for enabled feature at target application
   */
  useFeatureFlag: (feature: SparUIFeatureFlag) => { enabled: true } | { enabled: false; message?: string };

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
  }) => Promise<{ success: true } | { success: false; error: { type?: 'error' | 'notice'; message: string } }>;

  /**
   * Navigation helper
   * Supports optional search params for query strings
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
   * Get current search params
   */
  useSearchParamsFn: () => Record<string, unknown>;

  /**
   * Get current pathname
   */
  usePathnameFn: () => string;

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

  /**
   * track analytics
   */
  track?: (metrics: AnalyticsEvent, value?: string) => Promise<void>;
}
