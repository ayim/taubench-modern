import { createBasicAgentConfig } from '../client';
import { ActionPackage, McpServer, QuestionGroup, ToolDefinitionPayload, UpsertAgentPayload } from '../types';
import { createSimpleTool } from '../../sdk/tools';
import { SAI_AGENT_SETUP_RUNBOOK } from './agent-setup-runbooks/the-runbook';
import { AgentConfigurationOptions } from './types';

const SAI_AGENT_SETUP_NAME = 'sai-sdk-agent-setup';
const SAI_AGENT_SETUP_DESCRIPTION = 'Sai Expert Agent Setup';

type AgentSetupTools = {
  callbackSetNameAndDescription: (name: string, description: string) => void;
  callbackSetRunbook: (runbook: string) => void;
  callbackSetActionPackages: (actionPackages: ActionPackage[]) => void;
  callbackSetMcpServers: (mcpServers: McpServer[]) => void;
  callbackSetConversationStarter: (conversationStarter: string) => void;
  callbackSetConversationGuide: (conversationGuide: QuestionGroup[]) => void;
  callbackOnComplete: () => void;
};

/**
 * Utility function to create a basic ephemeral agent configuration
 */
export function createSaiAgentSetupConfig(options: AgentConfigurationOptions): UpsertAgentPayload {
  const runbook = SAI_AGENT_SETUP_RUNBOOK.replace(
    '{AVAILABLE_ACTION_PACKAGES_PLACEHOLDER}',
    options.agent_context?.availableActionPackages
      ?.map((actionPackage) => JSON.stringify(actionPackage))
      .join('\n\n') || '',
  ).replace(
    '{AVAILABLE_MCP_SERVERS_PLACEHOLDER}',
    options.agent_context?.availableMcpServers?.map((mcpServer) => JSON.stringify(mcpServer)).join('\n\n') || '',
  );

  const agentConfig = createBasicAgentConfig({
    name: options.name || SAI_AGENT_SETUP_NAME + Date.now().toString(),
    description: options.description || SAI_AGENT_SETUP_DESCRIPTION,
    runbook: options.runbook || runbook,
    platform_configs: options.platform_configs,
    agent_id: options.agent_id,
    agent_architecture: options.agent_architecture,
  });
  return agentConfig;
}

/**
 * Utility function to configure the tools for the agent setup
 */
export function configureSaiAgentSetupTools(agentSetupTools: AgentSetupTools): ToolDefinitionPayload[] {
  const tools: ToolDefinitionPayload[] = [];

  // Set the description of the agent
  const setNameAndDescriptionTool: ToolDefinitionPayload = createSimpleTool(
    'set_agent_name_and_description',
    '⚠️ PHASE 3 ONLY - DO NOT USE IN PHASE 1 OR 2 ⚠️ Set the name and description of the agent. Only call this tool after user has approved and moved to Phase 3.',
  )
    .addStringProperty('description', 'The description of the agent')
    .addStringProperty('name', 'The name of the agent')
    .addRequired('name')
    .addRequired('description')
    .setCallback((i) => {
      agentSetupTools.callbackSetNameAndDescription(i.name, i.description);
    })
    .setCategory('client-info-tool')
    .build();
  tools.push(setNameAndDescriptionTool);

  // Set the runbook of the agent
  const setRunbookTool: ToolDefinitionPayload = createSimpleTool(
    'set_agent_runbook',
    '⚠️ PHASE 3 ONLY - DO NOT USE IN PHASE 1 OR 2 ⚠️ Set the runbook of the agent. Only call this tool after user has approved and moved to Phase 3.',
  )
    .addStringProperty('runbook', 'The runbook of the agent')
    .addRequired('runbook')
    .setCallback((i) => agentSetupTools.callbackSetRunbook(i.runbook))
    .setCategory('client-info-tool')
    .build();
  tools.push(setRunbookTool);

  // Set the action packages of the agent
  const setActionPackagesTool: ToolDefinitionPayload = createSimpleTool(
    'set_agent_action_packages',
    '⚠️ PHASE 3 ONLY - DO NOT USE IN PHASE 1 OR 2 ⚠️ Set the action packages of the agent. Only call this tool after user has approved and moved to Phase 3.',
  )
    .addArrayProperty(
      'action_packages',
      {
        type: 'object',
        properties: {
          name: { type: 'string' },
          organization: { type: 'string' },
          version: { type: 'string' },
        },
        required: ['name', 'organization', 'version'],
      },
      'The action packages of the agent',
    )
    .addRequired('action_packages')
    .setCallback((i) => agentSetupTools.callbackSetActionPackages(i.action_packages))
    .setCategory('client-info-tool')
    .build();
  tools.push(setActionPackagesTool);

  // Set the MCP servers of the agent
  const setMcpServersTool: ToolDefinitionPayload = createSimpleTool(
    'set_agent_mcp_servers',
    '⚠️ PHASE 3 ONLY - DO NOT USE IN PHASE 1 OR 2 ⚠️ Set the MCP servers of the agent. Only call this tool after user has approved and moved to Phase 3.',
  )
    .addArrayProperty(
      'mcp_servers',
      {
        type: 'object',
        properties: { name: { type: 'string' } },
        required: ['name'],
      },
      'The MCP servers of the agent',
    )
    .addRequired('mcp_servers')
    .setCallback((i) => agentSetupTools.callbackSetMcpServers(i.mcp_servers))
    .setCategory('client-info-tool')
    .build();
  tools.push(setMcpServersTool);

  // Set the conversation starter of the agent
  const setConversationStarterTool: ToolDefinitionPayload = createSimpleTool(
    'set_agent_conversation_starter',
    '⚠️ PHASE 3 ONLY - DO NOT USE IN PHASE 1 OR 2 ⚠️ Set the conversation starter of the agent. Only call this tool after user has approved and moved to Phase 3.',
  )
    .addStringProperty('conversation_starter', 'The conversation starter of the agent')
    .addRequired('conversation_starter')
    .setCallback((i) => agentSetupTools.callbackSetConversationStarter(i.conversation_starter))
    .setCategory('client-info-tool')
    .build();
  tools.push(setConversationStarterTool);

  // Set the question groups of the agent
  const setQuestionGroupsTool: ToolDefinitionPayload = createSimpleTool(
    'set_agent_conversation_guide',
    '⚠️ PHASE 3 ONLY - DO NOT USE IN PHASE 1 OR 2 ⚠️ Set the question groups of the agent. Only call this tool after user has approved and moved to Phase 3.',
  )
    .addArrayProperty(
      'question_groups',
      {
        type: 'object',
        properties: { title: { type: 'string' }, questions: { type: 'array', items: { type: 'string' } } },
        required: ['title', 'questions'],
      },
      'The question groups of the agent',
    )
    .addRequired('question_groups')
    .setCallback((i) => agentSetupTools.callbackSetConversationGuide(i.question_groups))
    .setCategory('client-info-tool')
    .build();
  tools.push(setQuestionGroupsTool);

  // On complete
  const onCompleteTool: ToolDefinitionPayload = createSimpleTool(
    'on_complete',
    '⚠️ PHASE 3 ONLY - DO NOT USE IN PHASE 1 OR 2 ⚠️ To be called when the agent setup is complete (Step 7 of Phase 3). Only call this tool after all previous steps in Phase 3 are complete.',
  )
    .setCallback(() => agentSetupTools.callbackOnComplete())
    .setCategory('client-info-tool')
    .build();
  tools.push(onCompleteTool);

  return tools;
}
