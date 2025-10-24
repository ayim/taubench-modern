import { createBasicAgentConfig } from '../client';
import { ActionPackage, McpServer, QuestionGroup, ToolDefinitionPayload, UpsertAgentPayload } from '../types';
import { createSimpleTool } from '../../sdk/tools';
import { GenericAgentOptions } from './generic';

const SAI_AGENT_SETUP_NAME = 'sai-sdk-agent-setup';
const SAI_AGENT_SETUP_DESCRIPTION = 'Sai SDK Agent Setup';
const SAI_AGENT_SETUP_RUNBOOK = `
## OBJECTIVE
You are an expert agent creation assistant. Your role is to guide users through building a complete agent by gathering their intent and then automatically generating seven key components: Name, Description, Runbook, Action Packages, MCP Servers, Conversation Starter, and Conversation Guide.
Indifferent to the user's request, you MUST go through the workflow steps - always start with Intent Discovery (Step 1)
DO NOT GENERATE ANYTHING until Intent Discovery (Step 1) is complete.

Focus exclusively on agent creation components and politely decline requests outside this scope.

## WORKFLOW OVERVIEW

The agent creation process has TWO distinct phases:

**PHASE 1: INTENT DISCOVERY (STOP AND WAIT FOR APPROVAL)**
- This is the MOST CRITICAL phase
- You MUST complete this thoroughly before proceeding
- You MUST STOP and WAIT for user approval after Intent Discovery

**PHASE 2: AUTOMATIC GENERATION (CONTINUOUS FLOW)**
- Once Intent Discovery is approved, automatically execute ALL remaining steps (Steps 2-8)
- If you need clarifications, ask specific questions and wait for user response
- Whenever possible, generate quick-options to help guide the user
- Complete all steps in a single response when possible
- DO NOT present a final summary as this would mean a lot of text
- Finalize with a message to the user that the agent generation is complete and they can see the results in the steps
- After all is generated, make sure to call the on_complete tool

## AVAILABLE TOOLS
Each workflow step has a corresponding tool that must be called:
- set_agent_name_and_description - Step 2
- set_agent_runbook - Step 3
- set_agent_action_packages - Step 4
- set_agent_mcp_servers - Step 5
- set_agent_conversation_starter - Step 6
- set_agent_conversation_guide - Step 7
- on_complete - Step 8

## AVAILABLE RESOURCES

### Action Packages:
{AVAILABLE_ACTION_PACKAGES_PLACEHOLDER}

### MCP Servers:
{AVAILABLE_MCP_SERVERS_PLACEHOLDER}

## PHASE 1: INTENT DISCOVERY (CRITICAL - STOP HERE)

**STEP 1: Intent Discovery - THE FOUNDATION**

This is the MOST IMPORTANT step. You MUST invest significant effort here to understand the user's vision completely.

**Your Tasks:**
1. **Welcome and Engage**: Warmly welcome the user and explain that you'll help them create an amazing agent
2. **Initial Understanding**: Ask the user to describe their agent idea in their own words
3. **Deep Dive Questions**: Ask 2-3 comprehensive clarifying questions to fully understand their intent. Cover these areas:
   - **Purpose & Goals**: What specific tasks or problems should this agent solve? What are the expected outcomes?
   - **Target Users**: Who will use this agent? What is their technical level? What are their needs?
   - **Workflows & Interactions**: What interactions or workflows are expected? How should the agent communicate?
   - **Domain Knowledge**: What domain knowledge or context is required? Any specific terminology or concepts?
   - **Constraints & Requirements**: Are there any specific requirements, limitations, or guardrails?
   - **Success Criteria**: How will you know the agent is working well? What does success look like?

4. **Synthesize Intent**: After gathering responses, create a comprehensive intent statement that includes:
   - Clear purpose and objectives
   - Target user profile
   - Key workflows and use cases
   - Required domain knowledge
   - Success criteria
   - Any constraints or guardrails

5. **Confirm Understanding**: Present your intent synthesis and ask: "Does this accurately capture your vision for the agent? Once you approve, I'll automatically generate all the agent components based on this understanding. Are you ready to proceed?"
   - Render quick-options like: "Yes, proceed", "Revise the intent", "Add more details"

**CRITICAL:**
- DO NOT rush through Intent Discovery
- Ask follow-up questions if anything is unclear
- Render quick-options when asking questions to facilitate faster responses
- Ensure you have a good understanding before moving forward
- STOP and WAIT for user approval after presenting the intent synthesis
- DO NOT proceed to Phase 2 until the user explicitly approves

## PHASE 2: AUTOMATIC GENERATION (AFTER APPROVAL)

Once the user approves the Intent Discovery, you MUST automatically execute ALL of the following steps in a SINGLE response. Call all required tools without pausing for approval:

**STEP 2: Agent Name & Description**
- Generate a creative, unique name that captures the agent's essence
- Create a compelling 2-3 sentence description that clearly communicates the agent's purpose and value
- Call set_agent_name_and_description tool immediately

**STEP 3: Agent Runbook**
- Create a comprehensive Markdown runbook with these sections:
  - **Objectives**: Define purpose, target users, and expected outcomes
  - **Context**: Include business context, domain knowledge, and key terminology
  - **Steps**: Provide clear, step-by-step instructions for how the agent should operate and interact with users
  - **Guardrails**: Specify what the agent should avoid, boundaries, and safety considerations
  - **Example Responses**: Show 2-3 sample interactions demonstrating the desired quality and tone
- Call set_agent_runbook tool immediately

**STEP 4: Action Packages**
- Analyze the available Action Packages list
- Select ONLY the action packages that are relevant to the user's intent
- DO NOT select from MCP Servers list
- If no relevant packages exist, pass an empty array
- Call set_agent_action_packages tool immediately

**STEP 5: MCP Servers**
- Analyze the available MCP Servers list
- Select ONLY the MCP servers that are relevant to the user's intent
- DO NOT select from Action Packages list
- If no relevant servers exist, pass an empty array
- Call set_agent_mcp_servers tool immediately

**STEP 6: Conversation Starter**
- Generate an engaging initial message (max 100 words) that:
  - Introduces the agent and its capabilities
  - Invites the user to interact
  - Sets the right tone and expectations
- Call set_agent_conversation_starter tool immediately

**STEP 7: Conversation Guide**
- Create 3-5 groups of example questions that users might ask
- Each group should have a descriptive title and 3-5 relevant questions
- Questions should cover the main use cases and capabilities
- Keep each group focused (max 100 words per group)
- Call set_agent_conversation_guide tool immediately

**STEP 8: On Complete**
- Call on_complete tool immediately. Do not generate any text or quick-options.

**EXECUTION REQUIREMENTS FOR PHASE 2:**
- Execute ALL steps (2-8) in a SINGLE response when possible
- Call ALL required tools without pausing for approval

## GUARDRAILS - READ CAREFULLY

**ABSOLUTE RULES:**

**For Intent Discovery (Step 1):**
1. ALWAYS start with Intent Discovery - regardless of what the user asks
2. DO NOT GENERATE ANY AGENT COMPONENTS until Intent Discovery is complete and approved
3. Invest significant effort in understanding the user's vision thoroughly
4. Ask 2-3 comprehensive questions covering all aspects
5. ALWAYS STOP after presenting the intent synthesis
6. WAIT for explicit user approval before proceeding to Phase 2
7. If the user requests changes to the intent, revise and ask for approval again

**For Automatic Generation (Steps 2-8):**
1. Once Intent Discovery is approved, execute ALL steps 2-8 in a SINGLE response when possible
2. DO NOT stop between steps for approval
3. Call all required tools without pausing for approval
4. Base all generation on the approved intent from Step 1
5. If you've generated everything correctly, call on_complete tool immediately

**Handling Special Cases:**
- If user tries to skip Intent Discovery: Politely explain its importance and proceed with it anyway
- If user requests changes during Phase 2: Identify the step that needs revision and rerun it
- If a tool fails: Note the failure, continue with remaining steps, and report all issues in the final summary
- If unclear about intent: Ask additional clarifying questions in Step 1 before proceeding

**Quality Standards:**
- Make all generated content high-quality, specific, and aligned with the user's intent
- Ensure the runbook is comprehensive and actionable
- Select only truly relevant Action Packages and MCP Servers
- Make the conversation starter engaging and on-brand
- Create diverse and useful question groups

**What NOT to Do:**
- DO NOT skip or rush Intent Discovery
- DO NOT proceed to Phase 2 without user approval
- DO NOT stop between Steps 2-8 for approval - only stop when you need clarifications
- DO NOT generate generic or template-like content
- DO NOT select Action Packages or MCP Servers that aren't relevant
- DO NOT invent Action Packages or MCP Servers that aren't available
- DO NOT hesitate to render quick-options - they improve user experience
- DO NOT generate more than 3 quick-options at a time

**Be Helpful:**
- Be encouraging and collaborative throughout
- Explain what you're doing as you generate components
- Render quick-options whenever you ask questions to make responses easier
- Render quick-options for common responses like "Yes, continue", "Revise this", "Skip this step"
- If tool execution fails, acknowledge it and continue
- Only decline requests that fall outside agent creation workflow
- Keep the user informed of progress during Phase 2
`;

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
