/* eslint-disable max-len */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { ContextDefinitionBuilder } from '../context';
import { ScenarioContextBuilder, ScenarioContextType } from '../scenarioContext';
import { AGENT_SETUP_GENERATE_CONVERSATION_STARTER_INSTRUCTIONS } from './agentSetupGenConvStarter';
import { AGENT_SETUP_GENERATE_DESCRIPTION_INSTRUCTIONS } from './agentSetupGenDescription';
import { AGENT_SETUP_GENERATE_NAME_INSTRUCTIONS } from './agentSetupGenName';
import { AGENT_SETUP_GENERATE_CONVERSATION_GUIDE_INSTRUCTIONS } from './agentSetupGenConvGuide';
import { AGENT_SETUP_GENERATE_RUNBOOK_INSTRUCTIONS } from './agentSetupGenRunbook';
import { AGENT_SETUP_GENERATE_RUNBOOK_IMPROVEMENT_INSTRUCTIONS } from './agentSetupGenRunbookImprov';
import { AGENT_SETUP_GENERATE_RUNBOOK_SAI_WRITE_INSTRUCTIONS } from './agentSetupGenRunbookSaiWrite';
import { AGENT_SETUP_GENERATE_RUNBOOK_SAI_REWRITE_INSTRUCTIONS } from './agentSetupGenRunbookSaiRewrite';

// System Instructions
const AGENT_SETUP_GENERAL_INSTRUCTIONS = [
  `Do not think too much, be quick in your suggestions.`,
  `Focus on quality over quantity.`,
  `Follow this priority order: Agent Name, Agent Description, Agent Runbook, Agent Action Packages, Agent MCP Servers, Agent Conversation Starter, Agent Question Groups, Agent Conversation Guide.`,
];

// Prompts
export const AGENT_SETUP_PROMPTS = {
  generateName: [
    'Pick a business domain that the Agent can function in and a goal for the Agent.',
    'Be really creative and generate a name for an that doimain and goal.',
    'Use the set_name tool to set the name of the agent.',
  ].join('\n'),
  generateDescription: [
    'Write a description for the agent.',
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
    'Pick action packages and MCP servers (which are tools) based on Agent context',
    'The action suggestions are a list of actions that the agent can perform.',
    'Use the set_tools tool to set the tools for the agent.',
  ].join('\n'),
  generateRunbookImprovements: [
    `Generate a set of improvements for the current runbook.`,
    'Call the set_improvements tool to set the improvements for the runbook.',
  ].join('\n'),
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
  createAgentContext(): this {
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
      .setRawSystemInstructions(AGENT_SETUP_GENERATE_NAME_INSTRUCTIONS)
      .createAgentContext();
    return builder.buildContextBuilder('balanced');
  }
  /**
   * Create a context builder specifically for runbook generation
   */
  static forAgentDescriptionGeneration(agentData: AgentContextData): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .setRawSystemInstructions(AGENT_SETUP_GENERATE_DESCRIPTION_INSTRUCTIONS)
      .createAgentContext();
    return builder.buildContextBuilder('balanced');
  }

  /**
   * Create a context builder specifically for runbook generation
   */
  static forRunbookGeneration(
    agentData: AgentContextData,
    type: ScenarioContextType = 'creative',
  ): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .setRawSystemInstructions(AGENT_SETUP_GENERATE_RUNBOOK_INSTRUCTIONS)
      .createAgentContext();

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
      .createAgentContext()
      .setRawSystemInstructions(AGENT_SETUP_GENERATE_RUNBOOK_IMPROVEMENT_INSTRUCTIONS);

    return builder.buildContextBuilder(type);
  }

  /**
   * Create a context builder specifically for runbook generation
   */
  static forRunbookWriteWithSai(agentData: AgentContextData): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .setRawSystemInstructions(AGENT_SETUP_GENERATE_RUNBOOK_SAI_WRITE_INSTRUCTIONS)
      .createAgentContext();
    return builder.buildContextBuilder('creative');
  }

  /**
   * Create a context builder specifically for runbook generation
   */
  static forRunbookRewriteWithSai(agentData: AgentContextData, selectedText?: string): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .setRawSystemInstructions(AGENT_SETUP_GENERATE_RUNBOOK_SAI_REWRITE_INSTRUCTIONS)
      .addSection('Selected Text', selectedText || '')
      .createAgentContext();
    return builder.buildContextBuilder('creative');
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
        'Always call the set_tools tool to set the tools for the agent.',
      ])
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
        'Always pick at maximum 5 action packages.',
        'Always pick at maximum 5 MCP servers.',
        'Always respond with the action packages in the format of organization, name and version.',
        'Always call the set_tools tool to set the tools for the agent.',
      ])
      .createAgentContext();
    return builder.buildContextBuilder('creative');
  }

  /**
   * Create a context builder specifically for conversation starter generation
   */
  static forConversationStarter(agentData: AgentContextData): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .setRawSystemInstructions(AGENT_SETUP_GENERATE_CONVERSATION_STARTER_INSTRUCTIONS)
      .createAgentContext();

    return builder.buildContextBuilder('balanced');
  }

  /**
   * Create a context builder specifically for conversation guide generation
   */
  static forConversationGuide(agentData: AgentContextData): ContextDefinitionBuilder {
    const builder = new AgentSetupContextBuilder()
      .setAgentData(agentData)
      .setRawSystemInstructions(AGENT_SETUP_GENERATE_CONVERSATION_GUIDE_INSTRUCTIONS)
      .createAgentContext();

    return builder.buildContextBuilder('creative');
  }
}

export function createAgentSetupScenarioContext(): AgentSetupContextBuilder {
  return new AgentSetupContextBuilder();
}
