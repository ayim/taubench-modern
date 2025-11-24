import { AgentContext } from '../../types';
import { PlatformConfig } from '../../platform-config';
import { AgentArchitecture, ToolDefinitionPayload } from '../types';

/**
 * Configuration options for creating a generic agent
 */
export interface AgentConfigurationOptions {
  /** Platform configurations */
  platform_configs: PlatformConfig[];
  /** Agent ID for persistence (optional) */
  agent_id?: string;
  /** Custom name for the agent (optional) */
  name?: string;
  /** Custom description for the agent (optional) */
  description?: string;
  /** Custom runbook for the agent (optional, defaults to generic runbook) */
  runbook?: string;
  /** Agent architecture configuration (optional) */
  agent_architecture?: AgentArchitecture;
  /** Additional tools to include in the agent */
  client_tools?: ToolDefinitionPayload[];
  /** Custom sub-context for the agent (optional, defaults to empty string) */
  agent_context?: AgentContext;
}
