import { PlatformConfig } from '../../platform-config';
import { createBasicAgentConfig } from '../client';
import { ActionPackage, AgentArchitecture, McpServer, ToolDefinitionPayload, UpsertAgentPayload } from '../types';

const SAI_GENERIC_AGENT_NAME = 'sai-sdk-generic-agent';
const SAI_GENERIC_AGENT_DESCRIPTION = 'Sai General Purpose Agent';
const SAI_GENERIC_AGENT_RUNBOOK = `
## OBJECTIVE
You are Sai.
You are a helpful AI assistant designed to assist users with a wide variety of tasks. 
Your role is to provide accurate, clear, and actionable responses while maintaining a professional and friendly demeanor.

## CORE CAPABILITIES
- Answer questions across diverse topics
- Provide detailed explanations and guidance
- Execute tasks using available tools
- Adapt communication style to user needs
- Maintain context throughout conversations

## BEHAVIOR GUIDELINES

### Communication Style
- Be clear, concise, and professional
- Adapt complexity level to user's apparent knowledge
- Use examples and analogies when helpful
- Ask clarifying questions when requirements are ambiguous
- Acknowledge limitations when uncertain

### Task Execution
- Break down complex tasks into manageable steps
- Use available tools efficiently and appropriately
- Verify understanding before taking significant actions
- Provide progress updates for longer operations
- Confirm critical actions before execution

### Problem-Solving Approach
1. Understand the user's goal and constraints
2. Analyze available resources and tools
3. Propose a solution or approach
4. Execute with transparency
5. Verify results and adjust if needed

## AVAILABLE TOOLS
--------------------------------
{AVAILABLE_TOOLS_PLACEHOLDER}
--------------------------------

## SUB-CONTEXT
This section is for context that is not part of the main context but is relevant to the conversation.
This context is provided by the application and you should use it to help you answer the user's question.
--------------------------------
{SUB_CONTEXT_PLACEHOLDER}
--------------------------------

## INTERACTION GUIDELINES

### When Starting a Conversation
- Greet the user appropriately
- Understand their immediate need
- Ask clarifying questions if needed

### During the Conversation
- Stay focused on the user's goals
- Provide relevant information and context
- Use tools when they add value
- Keep responses well-structured

### When Completing Tasks
- Summarize what was accomplished
- Highlight any important outcomes or next steps
- Offer additional assistance

## GUARDRAILS

**What You Should Do:**
- Provide accurate, helpful information
- Use tools appropriately and efficiently
- Respect user preferences and constraints
- Admit when you don't know something
- Suggest alternatives when limitations exist

**What You Should Avoid:**
- Making assumptions without clarification
- Providing misleading or inaccurate information
- Executing irreversible actions without confirmation
- Ignoring context from previous messages
- Being unnecessarily verbose or overly brief

## ERROR HANDLING
- If a tool fails, explain the issue clearly
- Suggest alternative approaches when possible
- Ask for additional information if needed
- Maintain a helpful tone even when facing challenges

## QUALITY STANDARDS
- Accuracy: Provide correct and verified information
- Clarity: Communicate in an understandable way
- Efficiency: Accomplish tasks with minimal overhead
- Helpfulness: Prioritize user satisfaction and success
`;

/**
 * Configuration options for creating a generic agent
 */
export interface GenericAgentOptions {
  /** Platform configurations */
  platform_configs: PlatformConfig[];

  /** Custom name for the agent (optional) */
  name?: string;
  /** Custom description for the agent (optional) */
  description?: string;
  /** Custom runbook for the agent (optional, defaults to generic runbook) */
  runbook?: string;
  /** Custom sub-context for the agent (optional, defaults to empty string) */
  sub_context?: string;
  /** Agent ID for persistence (optional) */
  agent_id?: string;
  /** Available action packages for the agent (optional) */
  availableActionPackages?: ActionPackage[];
  /** Available MCP servers for the agent (optional) */
  availableMcpServers?: McpServer[];
  /** Agent architecture configuration (optional) */
  agent_architecture?: AgentArchitecture;
  /** Additional tools to include in the agent */
  client_tools?: ToolDefinitionPayload[];
}

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
export function createSaiGenericAgentConfig(options: GenericAgentOptions): UpsertAgentPayload {
  const {
    name,
    description,
    runbook: customRunbook,
    platform_configs,
    agent_id,
    agent_architecture,
    client_tools,
    sub_context,
  } = options;

  // Generate tools list for runbook if client_tools provided
  const toolsList =
    client_tools?.map((tool) => `- **${tool.name}**: ${tool.description}`).join('\n') ||
    'No additional tools configured';

  // Sub context should be a JSON string
  const finalSubContext = sub_context ? sub_context : 'No sub context provided';

  // Build the runbook with placeholders replaced
  const finalRunbook = (customRunbook || SAI_GENERIC_AGENT_RUNBOOK)
    .replace('{AVAILABLE_TOOLS_PLACEHOLDER}', toolsList)
    .replace('{SUB_CONTEXT_PLACEHOLDER}', finalSubContext);

  // Return the agent config
  return createBasicAgentConfig({
    name: name || SAI_GENERIC_AGENT_NAME + Date.now().toString(),
    description: description || SAI_GENERIC_AGENT_DESCRIPTION,
    runbook: finalRunbook,
    platform_configs,
    agent_id: agent_id,
    agent_architecture: agent_architecture,
  });
}
