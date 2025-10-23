import React, { useState, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { initializeSDK, createScenario, createContext, ScenarioTool, SaiSDK } from '../../src/index';
import { AGENT_SETUP_PROMPTS, AgentSetupContextBuilder } from '../../src/sdk/scenarios/agentSetupBuilder';

type Scenario =
  | 'generateName'
  | 'generateDescription'
  | 'generateRunbook'
  | 'generateConversationStarter'
  | 'generateQuestionGroups'
  | 'generateActionSuggestions'
  | 'generateRunbookImprovements';

type ScenarioContext = {
  agentName?: string;
  agentDescription?: string;
  agentRunbook?: string;
  agentConversationStarter?: string;
  agentQuestionGroups?: string;
  agentAvailableActions?: string;
  agentSelectedMcpServers?: string;
};

const ScenarioDetails = {
  generateName: {
    name: 'Generate a name for the agent',
    description: 'Generate a name for the agent',
  },
  generateDescription: {
    name: 'Generate a description for the agent',
    description: 'Generate a description for the agent',
  },
  generateRunbook: { name: 'Generate a runbook for the agent', description: 'Generate a runbook for the agent' },
  generateConversationStarter: {
    name: 'Generate a conversation starter for the agent',
    description: 'Generate a conversation starter for the agent',
  },
  generateQuestionGroups: {
    name: 'Generate question groups for the agent',
    description: 'Generate question groups for the agent',
  },
  generateActionSuggestions: {
    name: 'Generate action suggestions for the agent',
    description: 'Generate action suggestions for the agent',
  },
  generateRunbookImprovements: {
    name: 'Generate runbook improvements for the agent',
    description: 'Generate runbook improvements for the agent',
  },
};

export interface ScenarioDemoProps {
  scenario?: Scenario;
  apiKey: string;
  provider?: 'openai' | 'azure' | 'ollama' | 'anthropic' | 'cortex' | 'bedrock';
  model?: string;
  context?: ScenarioContext;
}

export const ScenarioDemo: React.FC<ScenarioDemoProps> = ({
  apiKey,
  model = 'gpt-4o',
  provider = 'openai',
  scenario = 'generateName',
  context,
}) => {
  const [isContextExpanded, setIsContextExpanded] = useState(true);

  // Scenario
  const [scenarioPrompt, setScenarioPrompt] = useState('');
  const [systemInstruction, setSystemInstruction] = useState('');

  // Context
  const [agentName, setAgentName] = useState('');
  const [agentDescription, setAgentDescription] = useState('');
  const [agentRunbook, setAgentRunbook] = useState('');
  const [agentAvailableActions, setAgentAvailableActions] = useState('');
  const [agentConversationStarter, setAgentConversationStarter] = useState('');
  const [agentQuestionGroups, setAgentQuestionGroups] = useState('');
  // Response
  const [response, setResponse] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamingUpdates, setStreamingUpdates] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [toolCalls, setToolCalls] = useState<{ toolName: string; input: any; inputValue: string }[]>([]);

  // Variables
  const scenarioName = ScenarioDetails[scenario].name;

  // Get the SDK Scenario Builder based on the scenario
  const getScenarioBuilder = useCallback(
    (scenario: Scenario, customSystemInstructions?: string, customPrompt?: string) => {
      switch (scenario) {
        case 'generateName': {
          return SaiSDK.createScenario(ScenarioDetails.generateName.name)
            .setPrompt(customPrompt || AGENT_SETUP_PROMPTS.generateName)
            .addTool(
              SaiSDK.createSimpleTool('set_name', 'Set the name of the agent')
                .addStringProperty('name', 'Name of the agent')
                .setRequired(['name'])
                .setCallback((input) => {
                  setToolCalls((prev) => [...prev, { toolName: 'set_name', input, inputValue: input.name }]);
                })
                .build(),
            )
            .setContext(
              AgentSetupContextBuilder.forAgentNameGeneration({
                agentName,
                agentDescription,
                agentRunbook,
                availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
                agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
                agentConversationStarter,
              }).build(),
            );
        }
        case 'generateDescription': {
          const prompt = customPrompt || AGENT_SETUP_PROMPTS.generateDescription;
          const systemInstruction: SaiSDK.Context = customSystemInstructions
            ? createContext().setSystemInstruction(customSystemInstructions).build()
            : AgentSetupContextBuilder.forAgentDescriptionGeneration({
                agentName,
                agentDescription,
                agentRunbook,
                availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
                agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
                agentConversationStarter,
              }).build();

          return SaiSDK.createScenario(ScenarioDetails.generateDescription.name)
            .setPrompt(prompt)
            .addTool(
              SaiSDK.createSimpleTool('set_description', 'Set the description of the agent')
                .addStringProperty('description', 'Description of the agent')
                .setRequired(['description'])
                .setCallback((input) => {
                  setToolCalls((prev) => [
                    ...prev,
                    { toolName: 'set_description', input, inputValue: input.description },
                  ]);
                })
                .build(),
            )
            .setContext(systemInstruction);
        }
        case 'generateRunbook': {
          const systemInstruction: SaiSDK.Context = customSystemInstructions
            ? createContext().setSystemInstruction(customSystemInstructions).build()
            : AgentSetupContextBuilder.forRunbookGeneration({
                agentName,
                agentDescription,
                agentRunbook,
                availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
                agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
                agentConversationStarter,
              }).build();
          return SaiSDK.createScenario(ScenarioDetails.generateRunbook.name)
            .setPrompt(customPrompt || AGENT_SETUP_PROMPTS.generateRunbook)
            .addTool(
              SaiSDK.createSimpleTool('set_runbook', 'Set the runbook of the agent')
                .addStringProperty('runbook', 'Runbook of the agent')
                .setRequired(['runbook'])
                .setCallback((input) => {
                  setToolCalls((prev) => [...prev, { toolName: 'set_runbook', input, inputValue: input.runbook }]);
                })
                .build(),
            )
            .setContext(systemInstruction);
        }
        case 'generateConversationStarter': {
          const systemInstruction: SaiSDK.Context = customSystemInstructions
            ? createContext().setSystemInstruction(customSystemInstructions).build()
            : AgentSetupContextBuilder.forConversationStarter({
                agentName,
                agentDescription,
                agentRunbook,
                availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
                agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
                agentConversationStarter,
              }).build();
          return SaiSDK.createScenario(ScenarioDetails.generateConversationStarter.name)
            .setPrompt(customPrompt || AGENT_SETUP_PROMPTS.generateConversationStarter)
            .addTool(
              SaiSDK.createSimpleTool('set_conversation_starter', 'Set the conversation starter of the agent')
                .addStringProperty('conversation_starter', 'Conversation starter of the agent')
                .setRequired(['conversation_starter'])
                .setCallback((input) => {
                  setToolCalls((prev) => [
                    ...prev,
                    { toolName: 'set_conversation_starter', input, inputValue: input.conversation_starter },
                  ]);
                })
                .build(),
            )
            .setContext(systemInstruction);
        }
        case 'generateQuestionGroups': {
          const systemInstruction: SaiSDK.Context = customSystemInstructions
            ? createContext().setSystemInstruction(customSystemInstructions).build()
            : AgentSetupContextBuilder.forConversationGuide({
                agentName,
                agentDescription,
                agentRunbook,
                availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
                agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
                agentConversationStarter,
              }).build();
          return SaiSDK.createScenario(ScenarioDetails.generateQuestionGroups.name)
            .setPrompt(customPrompt || AGENT_SETUP_PROMPTS.generateQuestionGroups)
            .addTool(
              SaiSDK.createSimpleTool('set_question_groups', 'Set the question groups of the agent')
                .addArrayProperty(
                  'question_groups',
                  {
                    type: 'object',
                    properties: {
                      name: { type: 'string' },
                      prompts: {
                        type: 'array',
                        items: {
                          type: 'object',
                          properties: {
                            question: { type: 'string' },
                          },
                        },
                      },
                    },
                    required: ['name', 'prompts', 'prompts.question'],
                  },
                  'Array of question groups with names and prompts',
                )
                .setRequired(['question_groups'])
                .setCallback((input) => {
                  setToolCalls((prev) => [
                    ...prev,
                    { toolName: 'set_question_groups', input, inputValue: `${JSON.stringify(input)}` },
                  ]);
                })
                .build(),
            )
            .setContext(systemInstruction);
        }
        case 'generateActionSuggestions': {
          const systemInstruction: SaiSDK.Context = customSystemInstructions
            ? createContext().setSystemInstruction(customSystemInstructions).build()
            : AgentSetupContextBuilder.forActionSuggestion({
                agentName,
                agentDescription,
                agentRunbook,
                availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
                agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
                agentConversationStarter,
              }).build();
          return SaiSDK.createScenario(ScenarioDetails.generateActionSuggestions.name)
            .setPrompt(customPrompt || AGENT_SETUP_PROMPTS.generateActionSuggestions)
            .addTool(
              SaiSDK.createSimpleTool('set_action_suggestions', 'Set the action suggestions of the agent')
                .addArrayProperty('action_packages', {
                  type: 'object',
                  properties: {
                    organization: { type: 'string' },
                    name: { type: 'string' },
                    version: { type: 'string' },
                  },
                })
                .addArrayProperty('mcp_servers', {
                  type: 'object',
                  properties: {
                    name: { type: 'string' },
                  },
                })
                .setRequired(['action_packages', 'mcp_servers'])
                .setCallback((input) => {
                  setToolCalls((prev) => [
                    ...prev,
                    { toolName: 'set_action_suggestions', input, inputValue: `${JSON.stringify(input)}` },
                  ]);
                })
                .build(),
            )
            .setContext(systemInstruction);
        }
        case 'generateRunbookImprovements': {
          const systemInstruction: SaiSDK.Context = customSystemInstructions
            ? createContext().setSystemInstruction(customSystemInstructions).build()
            : AgentSetupContextBuilder.forRunbookImprovementGeneration({
                agentName,
                agentDescription,
                agentRunbook,
                availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
                agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
                agentConversationStarter,
              }).build();
          return SaiSDK.createScenario(ScenarioDetails.generateRunbookImprovements.name)
            .setPrompt(customPrompt || AGENT_SETUP_PROMPTS.generateRunbookImprovements)
            .addTool(
              SaiSDK.createSimpleTool('set_runbook_improvements', 'Set the runbook improvements of the agent')
                .addArrayProperty('improvements', {
                  type: 'object',
                  properties: {
                    original: { type: 'string' },
                    improvement: { type: 'string' },
                  },
                })
                .setRequired(['improvements'])
                .setCallback((input) => {
                  setToolCalls((prev) => [
                    ...prev,
                    { toolName: 'set_runbook_improvements', input, inputValue: `${JSON.stringify(input)}` },
                  ]);
                })
                .build(),
            )
            .setContext(systemInstruction);
        }
        default:
          return null;
      }
    },
    [agentName, agentDescription],
  );

  const handleExecute = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResponse(null);
    setToolCalls([]);

    try {
      const builder = getScenarioBuilder(scenario, systemInstruction, scenarioPrompt);
      if (!builder) {
        throw new Error('Invalid scenario');
      }

      const result = await builder.execute();
      setResponse(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [getScenarioBuilder, scenario, systemInstruction, scenarioPrompt]);

  const handleStream = async () => {
    setStreaming(true);
    setError(null);
    setStreamingUpdates([]);
    setResponse(null);
    setToolCalls([]);

    try {
      const builder = getScenarioBuilder(scenario, systemInstruction, scenarioPrompt);
      if (!builder) {
        throw new Error('Invalid scenario');
      }

      for await (const update of builder.stream()) {
        setStreamingUpdates((prev) => [...prev, update]);

        if (update.type === 'final_response') {
          setResponse(update.data);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setStreaming(false);
    }
  };

  const initializeScenario = useCallback(async () => {
    try {
      switch (scenario) {
        case 'generateName': {
          setScenarioPrompt(AGENT_SETUP_PROMPTS.generateName);
          setSystemInstruction(
            AgentSetupContextBuilder.forAgentNameGeneration({
              agentName,
              agentDescription,
              agentRunbook,
              availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
              agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
              agentConversationStarter,
            }).build().system_instruction || '',
          );
          break;
        }
        case 'generateDescription': {
          setScenarioPrompt(AGENT_SETUP_PROMPTS.generateDescription);
          setSystemInstruction(
            AgentSetupContextBuilder.forAgentDescriptionGeneration({
              agentName,
              agentDescription,
              agentRunbook,
              availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
              agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
              agentConversationStarter,
            }).build().system_instruction || '',
          );
          break;
        }
        case 'generateRunbook': {
          setScenarioPrompt(AGENT_SETUP_PROMPTS.generateRunbook);
          setSystemInstruction(
            AgentSetupContextBuilder.forRunbookGeneration({
              agentName,
              agentDescription,
              agentRunbook,
              availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
              agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
              agentConversationStarter,
            }).build().system_instruction || '',
          );
          break;
        }
        case 'generateConversationStarter': {
          setScenarioPrompt(AGENT_SETUP_PROMPTS.generateConversationStarter);
          setSystemInstruction(
            AgentSetupContextBuilder.forConversationStarter({
              agentName,
              agentDescription,
              agentRunbook,
              availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
              agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
              agentConversationStarter,
            }).build().system_instruction || '',
          );
          break;
        }
        case 'generateQuestionGroups': {
          setScenarioPrompt(AGENT_SETUP_PROMPTS.generateQuestionGroups);
          setSystemInstruction(
            AgentSetupContextBuilder.forConversationGuide({
              agentName,
              agentDescription,
              agentRunbook,
              availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
              agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
              agentConversationStarter,
            }).build().system_instruction || '',
          );
          break;
        }
        case 'generateActionSuggestions': {
          setScenarioPrompt(AGENT_SETUP_PROMPTS.generateActionSuggestions);
          setSystemInstruction(
            AgentSetupContextBuilder.forActionSuggestion({
              agentName,
              agentDescription,
              agentRunbook,
              availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
              agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
              agentConversationStarter,
            }).build().system_instruction || '',
          );
          break;
        }

        case 'generateRunbookImprovements': {
          setScenarioPrompt(AGENT_SETUP_PROMPTS.generateRunbookImprovements);
          setSystemInstruction(
            AgentSetupContextBuilder.forRunbookImprovementGeneration({
              agentName,
              agentDescription,
              agentRunbook,
              availableActionPackages: agentAvailableActions ? JSON.parse(agentAvailableActions) : [],
              agentQuestionGroups: agentQuestionGroups ? JSON.parse(agentQuestionGroups) : [],
              agentConversationStarter,
            }).build().system_instruction || '',
          );
          break;
        }
        default: {
          throw new Error('Invalid scenario');
        }
      }
    } catch (err) {
      console.error('Failed to initialize scenario:', err);
    }
  }, [
    context,
    scenario,
    agentName,
    agentDescription,
    agentRunbook,
    agentConversationStarter,
    agentQuestionGroups,
    agentAvailableActions,
  ]);

  useEffect(() => {
    initializeScenario();
  }, [initializeScenario]);

  // Initialize SDK
  useEffect(() => {
    try {
      initializeSDK({
        promptClient: {
          baseUrl: '',
        },
        platformConfig: {
          kind: provider,
          openai_api_key: apiKey,
          models: {
            [provider]: [model],
          },
        },
        defaultModel: model,
        options: {
          debug: true,
        },
      });

      setAgentName(context?.agentName || '');
      setAgentDescription(context?.agentDescription || '');
      setAgentRunbook(context?.agentRunbook || '');
      setAgentConversationStarter(context?.agentConversationStarter || '');
      setAgentQuestionGroups(context?.agentQuestionGroups || '');
      setAgentAvailableActions(context?.agentAvailableActions || '');
    } catch (err) {
      console.error('Failed to initialize SDK:', err);
    }
  }, [apiKey, model, provider, context]);

  return (
    <div className="w-full mx-auto p-16 font-sans flex flex-row gap-5">
      <div className={`w-1/2 sticky top-16 self-start border-r-2 border-green-500 px-5`}>
        <h2 className="text-gray-800 mb-5 border-b-2 border-green-600 font-semibold pb-2.5">{`Scenario Demo - ${scenarioName}`}</h2>

        <div className="mb-4">
          <label className="block mb-1.5 text-gray-600">System Instruction:</label>
          <textarea
            value={systemInstruction}
            onChange={(e) => setSystemInstruction(e.target.value)}
            rows={2}
            placeholder="Enter system instruction..."
            className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
          />
        </div>

        <div className="mb-4">
          <label className="block mb-1.5 text-gray-600">Scenario Prompt:</label>
          <textarea
            value={scenarioPrompt}
            onChange={(e) => setScenarioPrompt(e.target.value)}
            rows={3}
            placeholder="Enter scenario prompt..."
            className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
          />
        </div>

        <div className="flex items-center justify-between mb-5 border-b-2 border-green-600 pb-2.5">
          <h2 className="text-gray-800 m-0">Context</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setAgentName('');
                setAgentDescription('');
                setAgentRunbook('');
                setAgentAvailableActions('');
                setAgentConversationStarter('');
                setAgentQuestionGroups('');
              }}
              className="px-3 py-1 border border-gray-300 rounded text-sm cursor-pointer transition-all duration-200 bg-white hover:bg-gray-100"
            >
              Clear Context
            </button>
            <button
              onClick={() => setIsContextExpanded(!isContextExpanded)}
              className="px-3 py-1 border border-gray-300 rounded text-sm cursor-pointer transition-all duration-200 bg-white hover:bg-gray-100"
            >
              {isContextExpanded ? '▼' : '▶'}
            </button>
          </div>
        </div>

        {isContextExpanded && (
          <>
            <div className="mb-4">
              <label className="block mb-1.5 text-gray-600">Agent Name:</label>
              <input
                type="text"
                value={agentName}
                onChange={(e) => setAgentName(e.target.value)}
                placeholder="Enter agent name..."
                className="w-full p-2.5 border border-gray-300 rounded text-sm box-border focus:border-green-500"
              />
            </div>

            <div className="mb-4">
              <label className="block mb-1.5 text-gray-600">Agent Description:</label>
              <textarea
                value={agentDescription}
                onChange={(e) => setAgentDescription(e.target.value)}
                rows={3}
                placeholder="Enter agent description..."
                className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
              />
            </div>

            <div className="mb-4">
              <label className="block mb-1.5 text-gray-600">Agent Runbook:</label>
              <textarea
                value={agentRunbook}
                onChange={(e) => setAgentRunbook(e.target.value)}
                rows={3}
                placeholder="Enter agent runbook..."
                className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
              />
            </div>
            <div className="mb-4">
              <label className="block mb-1.5 text-gray-600">Agent Available Actions:</label>
              <textarea
                value={agentAvailableActions}
                onChange={(e) => setAgentAvailableActions(e.target.value)}
                rows={3}
                placeholder="Enter agent available actions. These should be an array of objects with the following properties: name, organization, version."
                className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
              />
            </div>
            <div className="mb-4">
              <label className="block mb-1.5 text-gray-600">Agent Conversation Starter:</label>
              <textarea
                value={agentConversationStarter}
                onChange={(e) => setAgentConversationStarter(e.target.value)}
                rows={3}
                placeholder="Enter agent conversation starter..."
                className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
              />
            </div>
            <div className="mb-4">
              <label className="block mb-1.5 text-gray-600">Agent Question Groups:</label>
              <textarea
                value={agentQuestionGroups}
                onChange={(e) => setAgentQuestionGroups(e.target.value)}
                rows={3}
                placeholder="Enter agent question groups..."
                className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
              />
            </div>

            <div className="bg-green-500 w-full h-[2px]" />
          </>
        )}
        <div className="flex gap-2.5 my-5">
          <button
            onClick={handleExecute}
            disabled={loading || streaming}
            className="px-5 py-2.5 border-none rounded text-sm font-semibold cursor-pointer transition-all duration-200 bg-green-600 text-white hover:bg-green-700 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? 'Executing...' : 'Execute Scenario'}
          </button>
          <button
            onClick={handleStream}
            disabled={loading || streaming}
            className="px-5 py-2.5 border-none rounded text-sm font-semibold cursor-pointer transition-all duration-200 bg-gray-600 text-white hover:bg-gray-700 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {streaming ? 'Streaming...' : 'Stream Scenario'}
          </button>
        </div>
      </div>

      <div className="w-1/2">
        {error && (
          <div className="bg-red-100 text-red-900 p-4 rounded border border-red-200 my-5">
            <strong>Error:</strong> {error}
          </div>
        )}

        {streaming && streamingUpdates.length > 0 && (
          <div className="bg-green-100 p-4 rounded border border-green-200 my-4">
            <h3 className="mt-0 text-green-900">Streaming Updates ({streamingUpdates.length}):</h3>
            <div className="max-h-48 overflow-y-auto">
              {streamingUpdates.slice(-5).map((update, idx) => (
                <div key={idx} className="bg-white px-3 py-2 rounded mb-1.5 text-xs">
                  <strong className="text-green-600">{update.type}:</strong>{' '}
                  {update.type === 'tool_partial' && update.data.result && (
                    <span>Tool result: {JSON.stringify(update.data.result)}</span>
                  )}
                  {update.type === 'response_update' && update.currentResponse?.content && (
                    <span>
                      {update.currentResponse.content
                        .filter((c: any) => c.kind === 'text')
                        .map((c: any) => c.text)
                        .join('')
                        .slice(0, 100)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {toolCalls.length > 0 && (
          <div className="bg-yellow-100 p-4 rounded border border-yellow-200 my-4">
            <h3 className="mt-0 text-yellow-900">Tool Calls with Inputs:</h3>
            {toolCalls.map(({ toolName, input, inputValue }, idx) => (
              <div key={idx} className="mb-1.5 text-sm font-mono flex flex-row gap-2">
                <div className="w-auto bg-white px-3 py-2 rounded">{toolName}</div>
                <div className="flex flex-col gap-2 !break-words !break-all !whitespace-pre-wrap">
                  <div className="max-w-3/4 bg-white px-3 py-2 rounded">{JSON.stringify(input)}</div>
                  <div className="max-w-3/4 bg-white px-3 py-2 rounded prose prose-sm max-w-none ">
                    <ReactMarkdown
                      components={{
                        h1: ({ node, ...props }) => <h1 className="text-xl font-bold mb-2 mt-4" {...props} />,
                        h2: ({ node, ...props }) => <h2 className="text-lg font-bold mb-2 mt-3" {...props} />,
                        h3: ({ node, ...props }) => <h3 className="text-base font-bold mb-1 mt-2" {...props} />,
                        p: ({ node, ...props }) => <p className="mb-2 leading-relaxed" {...props} />,
                        ul: ({ node, ...props }) => <ul className="list-disc list-inside mb-2 space-y-1" {...props} />,
                        ol: ({ node, ...props }) => (
                          <ol className="list-decimal list-inside mb-2 space-y-1" {...props} />
                        ),
                        li: ({ node, ...props }) => <li className="ml-2" {...props} />,
                        code: ({ node, inline, ...props }: any) =>
                          inline ? (
                            <code className="bg-gray-100 px-1 py-0.5 rounded text-xs font-mono" {...props} />
                          ) : (
                            <code
                              className="block bg-gray-100 p-2 rounded text-xs font-mono overflow-x-auto mb-2"
                              {...props}
                            />
                          ),
                        pre: ({ node, ...props }) => (
                          <pre className="bg-gray-100 p-2 rounded overflow-x-auto mb-2" {...props} />
                        ),
                        blockquote: ({ node, ...props }) => (
                          <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2" {...props} />
                        ),
                        a: ({ node, ...props }) => <a className="text-green-600 hover:underline" {...props} />,
                        strong: ({ node, ...props }) => <strong className="font-bold" {...props} />,
                        em: ({ node, ...props }) => <em className="italic" {...props} />,
                      }}
                    >
                      {inputValue}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {response && !streaming && (
          <div className="bg-gray-100 p-5 rounded border border-gray-300 my-5">
            <h3 className="mt-0 text-gray-800">Response:</h3>
            <div className="my-4">
              {response.content?.map((content: any, idx: number) => (
                <div key={idx} className="mb-2.5">
                  {content.kind === 'text' && (
                    <div className="bg-white p-4 rounded border-l-4 border-green-600 whitespace-pre-wrap leading-relaxed">
                      {content.text}
                    </div>
                  )}
                  {content.kind === 'tool_use' && (
                    <div className="bg-green-50 p-2.5 rounded border-l-4 border-green-800 text-sm">
                      <strong>Tool Used:</strong> {content.tool_name}
                    </div>
                  )}
                </div>
              ))}
            </div>
            <details className="mt-4 cursor-pointer">
              <summary className="font-semibold text-gray-600 p-2.5 bg-gray-200 rounded">Raw Response (JSON)</summary>
              <pre className="bg-gray-900 text-gray-300 p-4 rounded overflow-x-auto text-xs mt-2.5">
                {JSON.stringify(response, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </div>
    </div>
  );
};
