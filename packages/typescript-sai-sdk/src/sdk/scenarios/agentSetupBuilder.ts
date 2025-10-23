/* eslint-disable max-len */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { ContextDefinitionBuilder } from '../context';
import { ScenarioContextBuilder, ScenarioContextType } from '../scenarioContext';

// System Instructions

const AGENT_SETUP_GENERAL_INSTRUCTIONS = [
  `Do not think too much, be quick in your suggestions.`,
  `Focus on quality over quantity.`,
  `Follow this priority order: Agent Name, Agent Description, Agent Runbook, Agent Action Packages, Agent MCP Servers, Agent Conversation Starter, Agent Question Groups, Agent Conversation Guide.`,
];
const AGENT_SETUP_RUNBOOK_INSTRUCTIONS = [
  `The Runbook should be a string in Markdown format that contains these sections: Objectives, Context, Steps, Guardrails, Example Responses.`,
  `The Runbook is the key to the Agent's functionality, so it needs to contain lots of details per section, explaining to the Agent how it should behave, what it should execute and how it should return responses. `,
  `In terms of Objectives: Describe the agent's purpose and context, consider who the agent will work with, what work they're accomplishing, expected Outcome. `,
  `In terms of Context: Include unique business context or non-public domain knowledge, this enhances the agent's accuracy and relevance. `,
  `In terms of Steps: outline the agent's tasks with step-by-step instructions - include user interaction details; tips for Steps: clear Instructions (Ensure each step is clear and specific, and avoid ambiguity), Break Down Tasks (Divide complex tasks into smaller, manageable steps), Consistent Terminology (Use consistent terms and phrases to avoid confusion), Highlight Key Points (Use bold, italics, and headlines to focus on key points). `,
  `In terms of Guardrails: Be specific about what the agent should avoid. `,
  `In terms of Example Responses: Provide examples to improve interaction accuracy and quality.`,
];

const AGENT_SETUP_RUNBOOK_IMPROVEMENT_INSTRUCTIONS = [
  `You will find the runbook within the agent context as a string in Markdown format.`,
  `Split the runbook into paragraphs. Always split based on new lines (\\n) or whitespaces (\\s).`,
  `Avoid titles, headings in your improvements - select only paragraphs & improve the text within the paragraphs.`,
  `The original string is the extracted snippet of text from the runbook that needs to be replaced.`,
  `The improvement is a string that is a replacement for the original string.`,
  `The improvement should be a string in Markdown format.`,
  `The improvement should target the agent's specific capabilities, its use cases and its intended purpose.`,
  `Each improvement should be unique and not very similar to the original string.`,
  `Generate a set of improvements.`,
  `Strive for quality over quantity.`,
  `Call the tool set_improvements to set the improvements for the runbook.`,
];

// Prompts

export const AGENT_SETUP_PROMPTS = {
  generateName: [
    'Pick a business domain that the Agent can function in and a goal for the Agent.',
    'Be really creative and generate a name for an that doimain and goal.',
    'Use the set_name tool to set the name of the agent.',
  ].join('\n'),
  generateDescription: [
    'Write a description for an agent.',
    'The description is a brief description of the work this agent performs.',
    'Use the set_description tool to set the description of the agent.',
  ].join('\n'),
  generateRunbook: [
    'Generate a runbook for the agent.',
    'The runbook is a detailed guide for the agent to follow.',
    'Use the set_runbook tool to set the runbook of the agent.',
  ].join('\n'),
  generateConversationStarter: [
    'Generate a conversation starter for the agent.',
    'The conversation starter is the first message the agent will send to the user.',
    'Use the set_conversation_starter tool to set the conversation starter of the agent.',
  ].join('\n'),
  generateQuestionGroups: [
    'Generate question groups for the agent.',
    'The question groups are a list of questions that the agent will ask the user.',
    'Use the set_question_groups tool to set the question groups of the agent.',
  ].join('\n'),
  generateActionSuggestions: [
    'Generate action suggestions for the agent.',
    'The action suggestions are a list of actions that the agent can perform.',
    'Use the set_action_suggestions tool to set the action suggestions of the agent.',
  ].join('\n'),
  generateRunbookImprovements: [`Generate a set of improvements for the current runbook.`].join('\n'),
};

/**
 * Agent configuration interface for context building
 */
export interface AgentContextData {
  agentName?: string;
  agentDescription?: string;
  agentRunbook?: string;
  agentConversationStarter?: string;
  agentQuestionGroups?: any[];
  selectedActionPackages?: any[];
  availableActionPackages?: any[];
  availableMcpServers?: any[];
  selectedMcpServers?: any[];
}

/**
 * Specialized context builder for Agent Setup scenarios
 */
export class AgentSetupContextBuilder extends ScenarioContextBuilder {
  private agentData: AgentContextData = {};

  /**
   * Set agent data from the agent configuration context
   */
  setAgentData(agentData: AgentContextData): this {
    this.agentData = { ...agentData };
    return this;
  }

  /**
   * Add agent-specific context information
   */
  addAgentContext(): this {
    const context: Record<string, any> = {};

    if (this.agentData.agentName) {
      context.agentName = this.agentData.agentName;
    }

    if (this.agentData.agentDescription) {
      context.agentDescription = this.agentData.agentDescription;
    }

    if (this.agentData.agentRunbook) {
      context.agentRunbook = this.agentData.agentRunbook;
    }

    if (this.agentData.agentConversationStarter) {
      context.agentConversationStarter = this.agentData.agentConversationStarter;
    }

    if (this.agentData.agentQuestionGroups && this.agentData.agentQuestionGroups.length > 0) {
      context.agentQuestionGroups = this.agentData.agentQuestionGroups;
    }

    if (this.agentData.selectedActionPackages && this.agentData.selectedActionPackages.length > 0) {
      context.selectedActionPackages = this.agentData.selectedActionPackages.map((pkg) => ({
        name: pkg.name,
        organization: pkg.organization,
        version: pkg.version,
        actions: pkg.actions?.map((action: any) => action.name) || [],
      }));
    }

    if (this.agentData.availableActionPackages && this.agentData.availableActionPackages.length > 0) {
      context.availableActionPackages = this.agentData.availableActionPackages.map((actionPackage) => ({
        name: actionPackage.name,
        organization: actionPackage.organization,
        version: actionPackage.version,
        description: actionPackage.description,
        actions: actionPackage.actions?.map((action: any) => action.name) || [],
      }));
    }

    if (this.agentData.selectedMcpServers && this.agentData.selectedMcpServers.length > 0) {
      context.selectedMcpServers = this.agentData.selectedMcpServers.map((mcpServer) => ({
        name: mcpServer.name,
        actions: mcpServer.tools,
      }));
    }

    if (this.agentData.availableMcpServers && this.agentData.availableMcpServers.length > 0) {
      context.availableMcpServers = this.agentData.availableMcpServers.map((mcpServer) => ({
        name: mcpServer.name,
        actions: mcpServer.tools,
      }));
    }

    return this.addContext(context);
  }

  /**
   * Add common agent setup objectives
   */
  addAgentSetupObjectives(customObjectives?: string[]): this {
    const defaultObjectives = [
      'You are an AI assistant specialized in helping users set up and configure AI agents.',
      'Your goal is to provide helpful suggestions and guidance for agent configuration.',
      'Focus on creating practical and effective agent configurations.',
    ];

    const objectives = customObjectives || defaultObjectives;
    return this.addObjectives(objectives);
  }

  /**
   * Add common agent setup guardrails
   */
  addAgentSetupGuardrails(customGuardrails?: string[]): this {
    const defaultGuardrails = [
      'Always provide suggestions that are practical and implementable.',
      'Respect the existing agent configuration and context.',
      'Keep suggestions concise and focused.',
      "Ensure suggestions align with the agent's intended purpose.",
    ];

    const guardrails = customGuardrails || defaultGuardrails;
    return this.addGuardrails(guardrails);
  }

  //   ================================================================
  //   ================================================================

  /**
   * Create a context builder specifically for agent name generation
   */
  static forAgentNameGeneration(agentData: AgentContextData): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .addAgentSetupObjectives([
        ...AGENT_SETUP_GENERAL_INSTRUCTIONS,
        `Generate a name for an agent based on the provided context`,
      ])
      .addAgentContext()
      .addAgentSetupGuardrails([
        'Be really creative and generate a name for an that doimain and goal.',
        'Always add a dash after the name and after it 5 word description of the Agent.',
        'Call the tool and set the name of the agent to the name you generated.',
      ]);

    return builder.buildContextBuilder('creative');
  }
  /**
   * Create a context builder specifically for runbook generation
   */
  static forAgentDescriptionGeneration(agentData: AgentContextData): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .addAgentSetupObjectives([
        ...AGENT_SETUP_GENERAL_INSTRUCTIONS,
        `Generate a description for an agent based on the provided context`,
      ])
      .addAgentContext()
      .addAgentSetupGuardrails([
        'The description should be concise and to the point.',
        'The description should be no more than 100 words.',
      ]);

    return builder.buildContextBuilder('balanced');
  }

  /**
   * Create a context builder specifically for runbook generation
   */
  static forRunbookGeneration(
    agentData: AgentContextData,
    type: ScenarioContextType = 'balanced',
  ): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .addAgentSetupObjectives([
        ...AGENT_SETUP_GENERAL_INSTRUCTIONS,
        `Generate a runbook for an agent that can ${agentData.agentDescription || 'assist users'}`,
      ])
      .addAgentContext()
      .addSteps(AGENT_SETUP_RUNBOOK_INSTRUCTIONS)
      .addAgentSetupGuardrails([
        'The runbook should be concise and to the point.',
        type === 'creative'
          ? 'The runbook should be no more than 1000 words.'
          : 'The runbook should be no more than 500 words.',
        "Focus on the agent's specific capabilities and use cases.",
      ]);

    return builder.buildContextBuilder(type);
  }

  /**
   * Create a context builder specifically for runbook improvement generation
   */
  static forRunbookImprovementGeneration(
    agentData: AgentContextData,
    type: ScenarioContextType = 'creative',
  ): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .addAgentSetupObjectives(AGENT_SETUP_RUNBOOK_IMPROVEMENT_INSTRUCTIONS)
      .addAgentContext();

    return builder.buildContextBuilder(type);
  }

  /**
   * Create a context builder specifically for runbook generation
   */
  static forRunbookWriteWithSai(agentData: AgentContextData): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .addAgentContext()
      .addAgentSetupObjectives([
        ...AGENT_SETUP_RUNBOOK_INSTRUCTIONS,
        'You are an AI assistant that writes runbook content based on user requests.',
        `Always generate the specific content the user asks for.`,
        `Your response will be inserted directly into the runbook document.`,
        `Write clear, actionable content that fits the user's request exactly.`,
      ])
      .addGuardrails([
        'Always provide the content the user requests - do not refuse to generate content.',
        'Generate only the specific content requested - not an entire runbook or additional sections.',
        'Your response must be ready for direct insertion into the runbook without modification.',
        'Do not include explanations about what you are doing - only provide the requested content.',
        'Use proper Markdown formatting when appropriate for the content type.',
      ]);

    return builder.buildContextBuilder('balanced');
  }

  /**
   * Create a context builder specifically for runbook generation
   */
  static forRunbookRewriteWithSai(agentData: AgentContextData, selectedText?: string): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .addAgentContext()
      .addAgentSetupObjectives([
        `Your primary objective is to rewrite the selected text: ${selectedText || ''} within the runbook`,
        `Only generate the text that should replace the selected text, nothing else.`,
      ]);

    return builder.buildContextBuilder('balanced');
  }

  /**
   * Create a context builder specifically for action package suggestions
   */
  static forActionSuggestion(agentData: AgentContextData): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .addAgentSetupObjectives([
        ...AGENT_SETUP_GENERAL_INSTRUCTIONS,
        'Suggest relevant action packages for the agent based on the provided context',
        'Suggest relevant MCP servers for the agent based on the provided context',
        "Consider the agent's functionality and recommend appropriate tools and integrations.",
      ])
      .addAgentContext()
      .addSteps([
        'Analyze the agent description and runbook and suggest action packages that would be useful.',
        'Analyze the available action packages and suggest the ones that are most relevant to the agent.',
        'Analyze the available MCP servers and suggest the ones that are most relevant to the agent.',
        "Prioritize action packages that directly support the agent's intended functionality.",
        'Consider both general-purpose tools and specialized integrations.',
      ])
      .addAgentSetupGuardrails([
        'Always pick from the available action packages. Do not make up action packages.',
        'Always pick the latest version of the action package.',
        'Always prioritize MCP servers over action packages & pick MCP servers that are most relevant to the agent.',
        'Be thorough and pick only the action packages that are relevant to the Agent.',
        'Never pick the same action package twice.',
        'Never pick action packages that have the same functionality, similar descriptions or actions.',
        'Prioritize quality over quantity in suggestions.',
        "Ensure suggested packages are practical for the agent's functionality",
        'Always pick at most 5 action packages.',
        'Always pick at most 5 MCP servers.',
        'Always respond with the action packages in the format of organization, name and version.',
      ]);

    return builder.buildContextBuilder('balanced');
  }

  /**
   * Create a context builder specifically for conversation starter generation
   */
  static forConversationStarter(agentData: AgentContextData): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .addAgentSetupObjectives([
        ...AGENT_SETUP_GENERAL_INSTRUCTIONS,
        'Generate an engaging conversation starter for the agent.',
        "Create a welcoming and informative first message that explains the agent's capabilities.",
      ])
      .addAgentContext()
      .addSteps([
        'Create a friendly and professional conversation starter.',
        "Mention the agent's key capabilities and how it can help users.",
        'Keep the message concise but informative.',
        "Use a tone that matches the agent's intended purpose.",
      ])
      .addAgentSetupGuardrails([
        'The conversation starter should be welcoming and professional.',
        'Keep the message under 50 words.',
        "Focus on the agent's most important capabilities.",
      ]);

    return builder.buildContextBuilder('balanced');
  }

  /**
   * Create a context builder specifically for conversation guide generation
   */
  static forConversationGuide(agentData: AgentContextData): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .addAgentSetupObjectives([
        ...AGENT_SETUP_GENERAL_INSTRUCTIONS,
        'Generate a conversation guide for the agent.',
        'Create a list of questions that will set the context and guide the agent to correct and intended responses.',
        'The conversation guide should be a list of questions that are no more than 100 words.',
        'The conversation guide should be a list of questions to the Agent.',
      ])
      .addAgentContext();

    return builder.buildContextBuilder('balanced');
  }
}

export function createAgentSetupScenarioContext(): AgentSetupContextBuilder {
  return new AgentSetupContextBuilder();
}
