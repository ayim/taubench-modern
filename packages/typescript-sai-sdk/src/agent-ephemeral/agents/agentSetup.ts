import { createBasicAgentConfig } from '../client';
import { ActionPackage, McpServer, QuestionGroup, ToolDefinitionPayload, UpsertAgentPayload } from '../types';
import { createSimpleTool } from '../../sdk/tools';
import { GenericAgentOptions } from './generic';
import { SAI_AGENT_SETUP_RUNBOOK } from './agentSetupRunbooks/agentSetupRunbook';

const SAI_AGENT_SETUP_NAME = 'sai-sdk-agent-setup';
const SAI_AGENT_SETUP_DESCRIPTION = 'Sai SDK Agent Setup';

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
export function createSaiAgentSetupConfig(options: GenericAgentOptions): UpsertAgentPayload {
  const runbook = SAI_AGENT_SETUP_RUNBOOK.replace(
    '{AVAILABLE_ACTION_PACKAGES_PLACEHOLDER}',
    options.availableActionPackages?.map((actionPackage) => JSON.stringify(actionPackage)).join('\n\n') || '',
  ).replace(
    '{AVAILABLE_MCP_SERVERS_PLACEHOLDER}',
    options.availableMcpServers?.map((mcpServer) => JSON.stringify(mcpServer)).join('\n\n') || '',
  );

  return createBasicAgentConfig({
    name: options.name || SAI_AGENT_SETUP_NAME + Date.now().toString(),
    description: options.description || SAI_AGENT_SETUP_DESCRIPTION,
    runbook: options.runbook || runbook,
    platform_configs: options.platform_configs,
    agent_id: options.agent_id,
    agent_architecture: options.agent_architecture,
  });
}

/**
 * Utility function to configure the tools for the agent setup
 */
export function configureSaiAgentSetupTools(agentSetupTools: AgentSetupTools): ToolDefinitionPayload[] {
  const tools: ToolDefinitionPayload[] = [];

  // Set the description of the agent
  const setNameAndDescriptionTool: ToolDefinitionPayload = createSimpleTool(
    'set_agent_name_and_description',
    'Set the name and description of the agent',
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
  const setRunbookTool: ToolDefinitionPayload = createSimpleTool('set_agent_runbook', 'Set the runbook of the agent')
    .addStringProperty('runbook', 'The runbook of the agent')
    .addRequired('runbook')
    .setCallback((i) => agentSetupTools.callbackSetRunbook(i.runbook))
    .setCategory('client-info-tool')
    .build();
  tools.push(setRunbookTool);

  // Set the action packages of the agent
  const setActionPackagesTool: ToolDefinitionPayload = createSimpleTool(
    'set_agent_action_packages',
    'Set the action packages of the agent',
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
    'Set the MCP servers of the agent',
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
    'Set the conversation starter of the agent',
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
    'Set the question groups of the agent',
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
    'To be called when the agent setup is complete',
  )
    .setCallback(() => agentSetupTools.callbackOnComplete())
    .setCategory('client-info-tool')
    .build();
  tools.push(onCompleteTool);

  return tools;
}
