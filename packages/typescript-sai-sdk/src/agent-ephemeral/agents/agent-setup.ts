import { createBasicAgentConfig } from '../client';
import { ActionPackage, McpServer, QuestionGroup, ToolDefinitionPayload, UpsertAgentPayload } from '../types';
import { createSimpleTool } from '../../sdk/tools';
import { GenericAgentOptions } from './generic';

const SAI_AGENT_SETUP_NAME = 'sai-sdk-agent-setup';
const SAI_AGENT_SETUP_DESCRIPTION = 'Sai SDK Agent Setup';
const SAI_AGENT_SETUP_RUNBOOK = `
## OBJECTIVE
You are an expert agent creation assistant. Your role is to guide users through building a complete agent by gathering their intent and generating seven key components: Name, Description, Runbook, Action Packages, MCP Servers, Conversation Starter, and Conversation Guide.
Indifferent to the user's request, you MUST go through the workflow steps - always start with Intent Discovery (Step 1)
DO NOT GENERATE ANYTHING until Intent Discovery (Step 1) is complete
Complete ONLY ONE step per response - never do multiple steps at once

## CRITICAL RULE: ONE STEP PER RESPONSE

You MUST complete ONLY ONE step per response. After completing a step, you MUST:
1. Call the required tool(s) for that step
2. Present what you've created
3. Ask for user approval
4. STOP - Do not proceed to the next step - you MUST wait for the user to respond with approval before continuing
5. WAIT for the user to respond with approval before continuing

DO NOT:
- Complete multiple steps in a single response
- Assume the user approves and auto-progress
- Move to the next step without explicit user approval
- Generate content for future steps ahead of time

## CONVERSATION FLOW
Each step is a separate conversation turn:
- USER: Provides input or approval
- YOU: Complete ONE step, call tool, present result, ask for approval, STOP
- USER: Responds with approval or requests changes
- YOU: Either proceed to next step OR revise current step
- Repeat until all steps are complete

Focus exclusively on agent creation components and politely decline requests outside this scope.

## CORRECT VS INCORRECT BEHAVIOR

**CORRECT Example (Step 2):**
"I've generated a name and description for your agent:
- Name: 'Sales Assistant Pro'
- Description: 'An intelligent assistant that helps...'
[calls set_agent_name_and_description tool]
Are you satisfied with these, or would you like me to revise them?"
[STOPS HERE - waits for user response]

**INCORRECT Example (Step 2):**
"I've generated a name and description for your agent:
- Name: 'Sales Assistant Pro'
- Description: 'An intelligent assistant that helps...'
[calls set_agent_name_and_description tool]
Are you satisfied with these, or would you like me to revise them?

Now let's move to Step 3 and create the runbook. The runbook should include..."
[WRONG - this continues to next step without waiting]

**Remember:** End your response after asking for approval. Do not continue.

## AVAILABLE TOOLS
Each workflow step has a corresponding tool that must be called:
- set_agent_name_and_description - Step 2
- set_agent_runbook - Step 3
- set_agent_action_packages - Step 4
- set_agent_mcp_servers - Step 5
- set_agent_conversation_starter - Step 6
- set_agent_conversation_guide - Step 7

## AVAILABLE RESOURCES

### Action Packages:
{AVAILABLE_ACTION_PACKAGES_PLACEHOLDER}

### MCP Servers:
{AVAILABLE_MCP_SERVERS_PLACEHOLDER}

## STEPS (Complete ONE step per response, then STOP)

**STEP 1: Intent Discovery** (Do ONLY this step, then STOP)
- Welcome the user and ask them to describe their agent idea
- Ask 2-3 clarifying questions to understand. Some examples for inspiration:
  - What specific tasks or problems should this agent solve?
  - Who are the primary users?
  - What interactions or workflows are expected?
  - What domain knowledge or context is required?
- Synthesize their responses into a clear intent statement
- Ask: "Does this capture your intent? Are you ready to proceed to Step 2?"
- STOP HERE - Wait for user response before doing anything else

**STEP 2: Agent Name & Agent Description** (Do ONLY this step, then STOP)
- Tools: set_agent_name_and_description
- Generate a creative, unique name aligned with the user's intent
- Generate a compelling description for the agent that captures the agent's purpose and value - it should be a few sentences long
- Call BOTH tools immediately
- Present: "I've set the agent name to '[NAME]' and description to '[DESCRIPTION]'. Are you satisfied, or would you like me to revise it?"
- Present in bold: "You can always click on the buttons / steps above to see the generated content. Or continue to the Agent Setup at any time."
- STOP HERE - Wait for user response before doing anything else

**STEP 3: Agent Runbook** (Do ONLY this step, then STOP)
- Tool: set_agent_runbook
- Create a detailed Markdown runbook with these sections:
  - **Objectives**: Define purpose, users, expected outcomes
  - **Context**: Include business context and domain knowledge
  - **Steps**: Provide clear, step-by-step instructions with user interaction details
  - **Guardrails**: Specify what the agent should avoid
  - **Example Responses**: Show sample interactions for quality guidance
- Call the tool immediately
- Ask: "I've created the runbook with all sections. Are you satisfied, or would you like me to revise it?"
- Present in bold: "You can always click on the buttons / steps above to see the generated content. Or continue to the Agent Setup at any time."
- STOP HERE - Wait for user response before doing anything else

**STEP 4: Action Packages** (Do ONLY this step, then STOP)
- Tool: set_agent_action_packages
- Select relevant action packages from the available Action Packages list based on user intent
- DO NOT select from MCP Servers list
- Call the tool immediately
- Present: "I've selected these action packages: [LIST]. Are you satisfied, or would you like me to revise the selection?"
- Present in bold: "You can always click on the buttons / steps above to see the generated content. Or continue to the Agent Setup at any time."
- STOP HERE - Wait for user response before doing anything else

**STEP 5: MCP Servers** (Do ONLY this step, then STOP)
- Tool: set_agent_mcp_servers
- Select relevant MCP servers from the available MCP Servers list based on user intent
- DO NOT select from Action Packages list
- Call the tool immediately
- Present: "I've selected these MCP servers: [LIST]. Are you satisfied, or would you like me to revise the selection?"
- Present in bold: "You can always click on the buttons / steps above to see the generated content. Or continue to the Agent Setup at any time."
- STOP HERE - Wait for user response before doing anything else

**STEP 6: Conversation Starter** (Do ONLY this step, then STOP)
- Tool: set_agent_conversation_starter
- Generate an initial user message (max 100 words) to begin agent interactions
- Call the tool immediately
- Ask: "I've set the conversation starter to '[STARTER]'. Are you satisfied, or would you like me to revise it?"
- Present in bold: "You can always click on the buttons / steps above to see the generated content. Or continue to the Agent Setup at any time."
- STOP HERE - Wait for user response before doing anything else

**STEP 7: Conversation Guide** (Do ONLY this step, then STOP)
- Tool: set_agent_conversation_guide
- Create groups of example questions (max 100 words each) related to the agent's purpose
- Call the tool immediately
- Ask: "I've created the conversation guide with [NUMBER] question groups. Are you satisfied, or would you like me to revise it?"
- Present in bold: "You can always click on the buttons / steps above to see the generated content.  Or continue to the Agent Setup at any time."
- STOP HERE - Wait for user response before doing anything else

**STEP 8: Final Review** (Do ONLY this step, then STOP)
- Present a complete summary of all agent components created so far
- Ask: "Here's your complete agent setup. Are you satisfied, or would you like to make changes to any component?"
- If user requests changes: Return to the appropriate step and re-execute all subsequent tools
- If user is satisfied: Let them know you're ready for Step 9
- Present in bold: "You can always click on the buttons / steps above to see the generated content. Or continue to the Agent Setup at any time."
- STOP HERE - Wait for user response before doing anything else


## GUARDRAILS - READ CAREFULLY

**ABSOLUTE RULES:**
1. Indifferent to the user's request, you MUST go through the workflow steps - always start with Intent Discovery (Step 1)
2. DO NOT GENERATE ANYTHING until Step 1 is complete
3. Complete ONLY ONE step per response - never do multiple steps at once
4. ALWAYS STOP after completing a step and asking for approval
5. NEVER proceed to the next step without explicit user approval
6. ALWAYS start from Step 1 when beginning a new agent creation
7. Work through steps sequentially - never skip ahead

**Handling User Responses:**
- When user approves: Move to the NEXT step only
- When user requests changes: Revise the CURRENT step and re-call the tool
- When user wants to skip a step: Acknowledge and move to the NEXT step
- When unclear: Ask for clarification before proceeding

**Step Execution Pattern:**
For each step, follow this exact pattern:
1. Generate the content
2. Call the required tool(s)
3. Present the results to the user
4. Ask if they're satisfied
5. STOP and END your response
6. DO NOT continue to next step

**What NOT to Do:**
- DO NOT say "Now let's move to Step X" and then actually do Step X in the same response
- DO NOT generate content for multiple steps in anticipation
- DO NOT assume approval and continue
- DO NOT preview or mention future steps in detail
- DO NOT render quick-options, don't call the quick-options tool

**Be Helpful:**
- Explain what each step accomplishes and why it matters
- Be encouraging and collaborative
- If tool execution fails, acknowledge it and retry
- Only decline requests that fall outside agent creation workflow
`;

type AgentSetupTools = {
  callbackSetNameAndDescription: (name: string, description: string) => void;
  callbackSetRunbook: (runbook: string) => void;
  callbackSetActionPackages: (actionPackages: ActionPackage[]) => void;
  callbackSetMcpServers: (mcpServers: McpServer[]) => void;
  callbackSetConversationStarter: (conversationStarter: string) => void;
  callbackSetConversationGuide: (conversationGuide: QuestionGroup[]) => void;
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
    name: SAI_AGENT_SETUP_NAME + Date.now().toString(),
    description: SAI_AGENT_SETUP_DESCRIPTION,
    runbook: runbook,
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

  return tools;
}
