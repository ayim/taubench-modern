import { AgentConfigurationOptions } from './types';
import { createBasicAgentConfig } from '../client';
import { UpsertAgentPayload } from '../types';
import {
  SAI_GENERIC_AGENT_DESCRIPTION,
  SAI_GENERIC_AGENT_NAME,
  SAI_GENERIC_AGENT_RUNBOOK,
} from './agent-generic-runbooks/the-runbook';

/**
 * Utility function to create a generic ephemeral agent configuration
 *
 * This function creates a flexible, general-purpose agent that can be customized
 * with various options. It follows the same pattern as the Agent Setup but is
 * designed for broader use cases.
 *
 * @param options - Configuration options for the generic agent
 * @returns Complete agent payload ready for ephemeral streaming
 *
 * @example
 * ```typescript
 * const agentConfig = createGenericAgentConfig({
 *   platform_configs: [myPlatformConfig],
 *   name: 'My Custom Assistant',
 *   description: 'A specialized assistant for my use case',
 *   client_tools: [tool1, tool2],
 * });
 * ```
 */
export function createSaiGenericAgentConfig(options: AgentConfigurationOptions): UpsertAgentPayload {
  const {
    name: customName,
    description: customDescription,
    runbook: customRunbook,
    platform_configs,
    agent_id,
    agent_architecture,
    client_tools,
    agent_context: agentContext,
  } = options;

  // Generate tools list for runbook if client_tools provided
  const toolsList =
    client_tools?.map((tool) => `- **${tool.name}**: ${tool.description}`).join('\n') ||
    'No additional tools configured';

  // Sub context should be a JSON string
  const finalSubContext = agentContext?.raw ? agentContext.raw : 'No sub context provided';

  // Build the runbook with placeholders replaced
  const finalRunbook = (customRunbook || SAI_GENERIC_AGENT_RUNBOOK)
    .replace('{AVAILABLE_TOOLS_PLACEHOLDER}', toolsList)
    .replace('{SUB_CONTEXT_PLACEHOLDER}', finalSubContext);

  // Return the agent config
  return createBasicAgentConfig({
    name: customName || SAI_GENERIC_AGENT_NAME + Date.now().toString(),
    description: customDescription || SAI_GENERIC_AGENT_DESCRIPTION,
    runbook: finalRunbook,
    platform_configs,
    agent_id: agent_id,
    agent_architecture: agent_architecture,
  });
}
