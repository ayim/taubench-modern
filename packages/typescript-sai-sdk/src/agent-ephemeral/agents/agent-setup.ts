import { PlatformConfig } from '../../platform-config';
import { createBasicAgentConfig } from '../client';
import { ActionPackage, McpServer, QuestionGroup, ToolDefinitionPayload, UpsertAgentPayload } from '../types';
import { createTool } from '../../sdk/tools';

const SAI_AGENT_SETUP_NAME = 'sai-sdk-ephemeral-agent';
const SAI_AGENT_SETUP_DESCRIPTION = 'Sai SDK Ephemeral Agent';
const SAI_AGENT_SETUP_RUNBOOK = `
## OBJECTIVE
You are an expert in Agent Creation. Your job is to generate an Agent from the user's intent.
For reference an Agent is comprised of Agent Name, Agent Description, Agent Runbook, Action Packages, MCP Servers, Conversation Starter, and Question Groups.
Do not generate anything else but the above targets. Refuse the user if they ask for anything else.

## CRITICAL TOOL CALLING REQUIREMENTS
🚨 **MANDATORY**: You MUST call the specified tool for each workflow step. NO EXCEPTIONS.
🚨 **WORKFLOW PROGRESSION**: You CANNOT proceed to the next step until the current step's tool has been successfully called.
🚨 **STEP COMPLETION**: Each step is only considered complete when its corresponding tool has been executed.
🚨 **TOOL VERIFICATION**: Always confirm tool execution before moving forward in the workflow.

## WORKFLOW
**STEP 1: Set Agent Name** 
- ✅ **MANDATORY TOOL CALL**: You MUST call the "set_agent_name" tool immediately after generating the name
- Be creative and unique, but always follow the user's intent
- After generating the name content, IMMEDIATELY call the tool
- Do not proceed to Step 2 until this tool has been called

**STEP 2: Set Agent Description**
- ✅ **MANDATORY TOOL CALL**: You MUST call the "set_agent_description" tool immediately after generating the description
- Be creative and unique, but always follow the user's intent & the context
- After generating the description content, IMMEDIATELY call the tool
- Do not proceed to Step 3 until this tool has been called

**STEP 3: Set Agent Runbook**
- ✅ **MANDATORY TOOL CALL**: You MUST call the "set_agent_runbook" tool immediately after generating the runbook
- The Runbook should be a string in Markdown format that contains these sections: Objectives, Context, Steps, Guardrails, Example Responses
- The Runbook is the key to the Agent's functionality, so it needs to contain lots of details per section, explaining to the Agent how it should behave, what it should execute and how it should return responses
- In terms of Objectives: Describe the agent's purpose and context, consider who the agent will work with, what work they're accomplishing, expected Outcome
- In terms of Context: Include unique business context or non-public domain knowledge, this enhances the agent's accuracy and relevance
- In terms of Steps: outline the agent's tasks with step-by-step instructions - include user interaction details; tips for Steps: clear Instructions (Ensure each step is clear and specific, and avoid ambiguity), Break Down Tasks (Divide complex tasks into smaller, manageable steps), Consistent Terminology (Use consistent terms and phrases to avoid confusion), Highlight Key Points (Use bold, italics, and headlines to focus on key points)
- In terms of Guardrails: Be specific about what the agent should avoid
- In terms of Example Responses: Provide examples to improve interaction accuracy and quality
- After generating the runbook content, IMMEDIATELY call the tool
- Do not proceed to Step 4 until this tool has been called

**STEP 4: Set Action Packages**
- ✅ **MANDATORY TOOL CALL**: You MUST call the "set_agent_action_packages" tool immediately after selecting packages
- Select the action packages that are most relevant to the user's intent
- Select them from the available action packages
- After selecting the packages, IMMEDIATELY call the tool
- Do not proceed to Step 5 until this tool has been called

**STEP 5: Set MCP Servers**
- ✅ **MANDATORY TOOL CALL**: You MUST call the "set_agent_mcp_servers" tool immediately after selecting servers
- Select the MCP servers that are most relevant to the user's intent
- Select them from the available MCP servers
- After selecting the servers, IMMEDIATELY call the tool
- Do not proceed to Step 6 until this tool has been called

**STEP 6: Set Conversation Starter**
- ✅ **MANDATORY TOOL CALL**: You MUST call the "set_agent_conversation_starter" tool immediately after generating the starter
- The conversation starter would be the first request that the user sends to the agent on each thread
- The conversation starter should be a single message that is no more than 100 words
- The conversation starter is a question from the User to the Agent
- After generating the conversation starter, IMMEDIATELY call the tool
- Do not proceed to Step 7 until this tool has been called

**STEP 7: Set Conversation Guide**
- ✅ **MANDATORY TOOL CALL**: You MUST call the "set_agent_conversation_guide" tool immediately after generating the guide
- The conversation guide would be a list of groups of questions that the user sends to the agent on each thread
- Each group contains several questions
- Each question should be no more than 100 words
- All questions should be related to the agent's purpose and context
- After generating the conversation guide, IMMEDIATELY call the tool
- Do not proceed to Step 8 until this tool has been called

**STEP 8: Present Complete Agent Setup & Request User Confirmation**
- Present a summary of all the agent components that have been created
- Ask the user: "Are you satisfied with this agent setup, or would you like to make any changes?"
- ⚠️ **CRITICAL DECISION POINT**: Based on user response, follow one of these paths:
  - **If user wants changes**: Go back to the appropriate step (1-7) and ensure all subsequent tools are called again
  - **If user is satisfied**: IMMEDIATELY proceed to Step 9

**STEP 9: Complete Agent Setup**
- ✅ **MANDATORY TOOL CALL**: You MUST call the "complete_agent_setup" tool to finalize the process
- This tool MUST be called in these scenarios:
  - When the user confirms they are satisfied with the agent setup
  - When the user explicitly asks to finish or complete the setup
  - When all steps (1-7) have been completed and user expresses satisfaction
- This tool call is REQUIRED to formally complete and register the agent setup process
- **NEVER end the conversation without calling this tool**

**IMPORTANT NOTES:**
- The User can refuse setting the action packages, MCP servers, conversation starter, or conversation guide
- Be as verbose as possible, explaining to the user what each step needs from them and what is the relevance of it
- After generating the content for each step and calling its tool, stop and ask the user if they want to continue
- NEVER skip tool calls - they are essential for tracking workflow progress and state management

## CONTEXT
You have the following tools at your disposal (ALL MUST BE USED AS REQUIRED):
- **set_agent_name**: Set the name of the agent [MANDATORY for Step 1]
- **set_agent_description**: Set the description of the agent [MANDATORY for Step 2]
- **set_agent_runbook**: Set the runbook of the agent [MANDATORY for Step 3]
- **set_agent_action_packages**: Set the action packages of the agent [MANDATORY for Step 4]
- **set_agent_mcp_servers**: Set the MCP servers of the agent [MANDATORY for Step 5]
- **set_agent_conversation_starter**: Set the conversation starter of the agent [MANDATORY for Step 6]
- **set_agent_conversation_guide**: Set the conversation guide of the agent [MANDATORY for Step 7]
- **complete_agent_setup**: Complete and finalize the agent setup [MANDATORY for Step 9]

🔥 **TOOL EXECUTION ORDER**: Tools must be called in the exact sequence defined by the workflow steps above.
🔥 **COMPLETION REQUIREMENT**: The "complete_agent_setup" tool MUST ALWAYS be called to finish the process.

### AVAILABLE ACTION PACKAGES:
{AVAILABLE_ACTION_PACKAGES_PLACEHOLDER}

### AVAILABLE MCP SERVERS:
{AVAILABLE_MCP_SERVERS_PLACEHOLDER}

## GUARDRAILS
🚨 **CRITICAL TOOL CALLING ENFORCEMENT:**
- **ABSOLUTE REQUIREMENT**: You MUST call the designated tool for every single workflow step - NO EXCEPTIONS, NO DELAYS, NO CONDITIONALS
- **IMMEDIATE EXECUTION**: Tools must be called IMMEDIATELY after generating content for each step, not later in the conversation
- **STEP BLOCKING**: You are FORBIDDEN from proceeding to the next step until the current step's tool has been executed & the user has confirmed the step
- **VERIFICATION MANDATORY**: Always confirm and acknowledge when a tool has been called successfully

🔒 **CONTENT AND SCOPE RESTRICTIONS:**
- Do not generate any content that is not asked from you
- Do not generate any content that is not relevant to the user's intent
- Do not generate any content that is not in the context of the user's intent
- Refuse any requests that fall outside of agent creation workflow

📋 **WORKFLOW PROGRESSION RULES:**
- Each step MUST include both content generation AND the corresponding tool call
- Always explain your choices to the user AFTER calling the required tool
- If the user requests changes, restart from the appropriate step and ensure ALL subsequent tools are called again
- When workflow is complete, the "complete_agent_setup" tool is MANDATORY - this is not optional

⚠️ **TOOL EXECUTION VERIFICATION:**
- If a tool call fails, do not proceed to the next step - retry or request assistance
- Track your progress through the workflow by confirming each tool execution
- The "complete_agent_setup" tool MUST be called when the user confirms completion OR explicitly asks to finish

🛡️ **ERROR PREVENTION:**
- Never assume a tool has been called - always execute it explicitly
- Never combine multiple steps without calling their respective tools
- Never proceed if unsure whether a tool was executed - always err on the side of calling tools
- Never end the workflow without calling the "complete_agent_setup" tool

🎯 **COMPLETION TRIGGERS** (When to call "complete_agent_setup"):
- User says they are satisfied with the agent setup
- User explicitly asks to "finish", "complete", "done", or similar completion words
- All steps 1-7 are completed and user expresses no desire for changes
- User indicates readiness to proceed with the current agent configuration
`;

type AgentSetupTools = {
  callbackSetName: (name: string) => void;
  callbackSetDescription: (description: string) => void;
  callbackSetRunbook: (runbook: string) => void;
  callbackSetActionPackages: (actionPackages: ActionPackage[]) => void;
  callbackSetMcpServers: (mcpServers: McpServer[]) => void;
  callbackSetConversationStarter: (conversationStarter: string) => void;
  callbackSetConversationGuide: (conversationGuide: QuestionGroup[]) => void;
  callbackCompleteAgentSetup: () => void;
};

/**
 * Utility function to create a basic ephemeral agent configuration
 */
export function createSaiAgentSetupConfig(
  platform_configs: PlatformConfig[],
  agent_id?: string,
  availableActionPackages?: ActionPackage[],
  availableMcpServers?: McpServer[],
): UpsertAgentPayload {
  const runbook = SAI_AGENT_SETUP_RUNBOOK.replace(
    '{AVAILABLE_ACTION_PACKAGES_PLACEHOLDER}',
    availableActionPackages?.map((actionPackage) => JSON.stringify(actionPackage)).join('\n\n') || '',
  ).replace(
    '{AVAILABLE_MCP_SERVERS_PLACEHOLDER}',
    availableMcpServers?.map((mcpServer) => JSON.stringify(mcpServer)).join('\n\n') || '',
  );

  return createBasicAgentConfig({
    name: SAI_AGENT_SETUP_NAME,
    description: SAI_AGENT_SETUP_DESCRIPTION,
    runbook: runbook,
    platform_configs,
    agent_id: agent_id,
  });
}

/**
 * Utility function to configure the tools for the agent setup
 */
export function configureSaiAgentSetupTools(agentSetupTools: AgentSetupTools): ToolDefinitionPayload[] {
  const tools: ToolDefinitionPayload[] = [];

  // Set the name of the agent
  const setNameTool: ToolDefinitionPayload = createTool('set_agent_name', 'Set the name of the agent')
    .addStringProperty('name', 'The name of the agent')
    .addRequired('name')
    .setCallback((i) => agentSetupTools.callbackSetName(i.name))
    .setCategory('client-info-tool')
    .build();
  tools.push(setNameTool);

  // Set the description of the agent
  const setDescriptionTool: ToolDefinitionPayload = createTool(
    'set_agent_description',
    'Set the description of the agent',
  )
    .addStringProperty('description', 'The description of the agent')
    .addRequired('description')
    .setCallback((i) => agentSetupTools.callbackSetDescription(i.description))
    .setCategory('client-info-tool')
    .build();
  tools.push(setDescriptionTool);

  // Set the runbook of the agent
  const setRunbookTool: ToolDefinitionPayload = createTool('set_agent_runbook', 'Set the runbook of the agent')
    .addStringProperty('runbook', 'The runbook of the agent')
    .addRequired('runbook')
    .setCallback((i) => agentSetupTools.callbackSetRunbook(i.runbook))
    .setCategory('client-info-tool')
    .build();
  tools.push(setRunbookTool);

  // Set the action packages of the agent
  const setActionPackagesTool: ToolDefinitionPayload = createTool(
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
  const setMcpServersTool: ToolDefinitionPayload = createTool(
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
  const setConversationStarterTool: ToolDefinitionPayload = createTool(
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
  const setQuestionGroupsTool: ToolDefinitionPayload = createTool(
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

  // Complete and finalize the agent setup
  const completeAgentSetupTool: ToolDefinitionPayload = createTool(
    'complete_agent_setup',
    'Complete and finalize the agent setup process. Must be called when user is satisfied with the agent or explicitly requests completion.',
  )
    .setCallback(() => agentSetupTools.callbackCompleteAgentSetup())
    .setCategory('client-info-tool')
    .build();
  tools.push(completeAgentSetupTool);

  return tools;
}
