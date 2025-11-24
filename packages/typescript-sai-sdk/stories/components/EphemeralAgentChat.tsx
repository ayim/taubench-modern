import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  EphemeralAgentClient,
  createBasicAgentConfig,
  createUserThreadMessage,
  SaiAgentEphemeral,
  createSaiAgentSetupConfig,
  AgentContext,
} from '../../src/index';
import type { ToolDefinitionPayload } from '../../src/agent-ephemeral/types';
import { AGENT_SETUP_CONTEXT } from '../helpers/context';
import { createSaiGenericAgentConfig } from '../../src/agent-ephemeral/agents/agent-generic';
import { createSaiAgentRunbookEditorConfig } from '../../src/agent-ephemeral/agents/agent-runbook-editor';
import {
  EphemeralAgentRunbookEditor,
  EphemeralAgentSetup,
  EphemeralGeneric,
} from '../../src/agent-ephemeral/ephemeral-agents';

const CONVERSATION_GUIDE = [
  'Build an agent that uses Wikipedia for fact-checking.',
  'Build an agent that retrieves transcripts from YouTube videos and provides a summary.',
  'Build an agent that uses Zendesk to help with customer support.',
];

export interface EphemeralAgentChatProps {
  baseUrl: string;
  apiKey: string;
  model?: string;
  provider?: 'openai' | 'azure' | 'ollama' | 'anthropic' | 'cortex' | 'bedrock';
  agentType?: 'void' | 'generic' | 'agentSetup' | 'agentRunbookEditor';
  agentContext?: AgentContext;
}

export const EphemeralAgentChat: React.FC<EphemeralAgentChatProps> = ({
  baseUrl,
  apiKey,
  model = 'gpt-4o',
  provider = 'openai',
  agentType = 'void',
  agentContext = AGENT_SETUP_CONTEXT,
}) => {
  const [messages, setMessages] = useState<SaiAgentEphemeral.ThreadMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentName, setAgentName] = useState(AGENT_SETUP_CONTEXT.agentName);
  const [agentDescription, setAgentDescription] = useState(AGENT_SETUP_CONTEXT.agentDescription);
  const [agentRunbook, setAgentRunbook] = useState(AGENT_SETUP_CONTEXT.agentRunbook);
  const [toolCalls, setToolCalls] = useState<any[]>([]);
  const [isContextExpanded, setIsContextExpanded] = useState(false);

  // Context
  const [contextAgentName, setContextAgentName] = useState(agentContext.agentName);
  const [contextAgentDescription, setContextAgentDescription] = useState(agentContext.agentDescription);
  const [contextAgentRunbook, setContextAgentRunbook] = useState(agentContext.agentRunbook);
  const [contextAgentAvailableActions, setContextAgentAvailableActions] = useState(
    agentContext.availableActionPackages,
  );
  const [contextAgentAvailableMcpServers, setContextAgentAvailableMcpServers] = useState(
    agentContext.availableMcpServers,
  );
  const [contextAgentConversationStarter, setContextAgentConversationStarter] = useState(
    agentContext.agentConversationStarter,
  );
  const [contextAgentQuestionGroups, setContextAgentQuestionGroups] = useState(agentContext.agentQuestionGroups);
  const [contextAgentModel, setContextAgentModel] = useState(agentContext.agentModel || model);
  const [contextAgentModelProvider, setContextAgentModelProvider] = useState(
    agentContext.agentModelProvider || provider,
  );

  const streamRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageInputRef = useRef<HTMLTextAreaElement>(null);

  const handleSendMessage = useCallback(async () => {
    if (!input.trim()) return;

    const userMessage: SaiAgentEphemeral.ThreadMessage = createUserThreadMessage(input);

    setMessages((prev) => [...prev, userMessage]);
    setStreaming(true);
    setError(null);

    try {
      const client = new EphemeralAgentClient({
        baseUrl: baseUrl,
        verbose: true,
      });

      let clientTools: ToolDefinitionPayload[] = [];

      console.log('>>>> model', model);
      console.log('>>>> agentName', agentName);
      console.log('>>>> agentDescription', agentDescription);
      console.log('>>>> agentRunbook', agentRunbook);

      let agentConfig = createBasicAgentConfig({
        agent_architecture: {
          name: 'agent_platform.architectures.experimental_1',
          version: '0.0.1',
        },
        name: agentName || '',
        description: agentDescription || '',
        runbook: agentRunbook || '',
        platform_configs: [
          {
            kind: provider,
            openai_api_key: apiKey,
            models: {
              [provider]: [model],
            },
          },
        ],
      });
      switch (agentType) {
        case 'void':
          clientTools = [];
          break;
        case 'generic':
          agentConfig = createSaiGenericAgentConfig({
            agent_architecture: {
              name: 'agent_platform.architectures.experimental_1',
              version: '0.0.1',
            },
            name: agentName,
            description: agentDescription,
            runbook: agentRunbook,
            platform_configs: [
              {
                kind: provider,
                openai_api_key: apiKey,
                models: {
                  [provider]: [model],
                },
              },
            ],
          });
          clientTools = [];
          break;
        case 'agentSetup':
          agentConfig = createSaiAgentSetupConfig({
            agent_architecture: {
              name: 'agent_platform.architectures.experimental_1',
              version: '0.0.1',
            },
            name: agentName,
            description: agentDescription,
            runbook: agentRunbook,
            platform_configs: [
              {
                kind: provider,
                openai_api_key: apiKey,
                models: {
                  [provider]: [model],
                },
              },
            ],
          });
          clientTools = SaiAgentEphemeral.configureSaiAgentSetupTools({
            callbackSetNameAndDescription: (name: string, description: string) => {
              // console.warn('[TEST - CLIENT TOOLS] Set name and description:', name, description);
              const toolCallMsg = `set_name_and_description called with name: ${name} and description: ${description}`;
              setToolCalls((prev) => [...prev, toolCallMsg]);
            },
            callbackSetRunbook: (runbook: string) => {
              // console.warn('[TEST - CLIENT TOOLS] Set runbook:', runbook);
              const toolCallMsg = `set_runbook called with runbook: ${runbook}`;
              setToolCalls((prev) => [...prev, toolCallMsg]);
            },
            callbackSetActionPackages: (actionPackages: SaiAgentEphemeral.ActionPackage[]) => {
              // console.warn('[TEST - CLIENT TOOLS] Set action packages:', actionPackages);
              const toolCallMsg = `set_action_packages called with action packages: ${actionPackages.map((actionPackage) => actionPackage.name).join(', ')}`;
              setToolCalls((prev) => [...prev, toolCallMsg]);
            },
            callbackSetMcpServers: (mcpServers: SaiAgentEphemeral.McpServer[]) => {
              // console.warn('[TEST - CLIENT TOOLS] Set MCP servers:', mcpServers);
              const toolCallMsg = `set_mcp_servers called with MCP servers: ${mcpServers.map((mcpServer) => mcpServer.name).join(', ')}`;
              setToolCalls((prev) => [...prev, toolCallMsg]);
            },
            callbackSetConversationStarter: (conversationStarter: string) => {
              // console.warn('[TEST - CLIENT TOOLS] Set conversation starter:', conversationStarter);
              const toolCallMsg = `set_conversation_starter called with conversation starter: ${conversationStarter}`;
              setToolCalls((prev) => [...prev, toolCallMsg]);
            },
            callbackSetConversationGuide: (conversationGuide: SaiAgentEphemeral.QuestionGroup[]) => {
              // console.warn('[TEST - CLIENT TOOLS] Set conversation guide:', conversationGuide);
              const toolCallMsg = `set_conversation_guide called with conversation guide: ${conversationGuide
                .map((questionGroup) => {
                  return `Title: ${questionGroup.title} & Questions: ${questionGroup?.questions?.join(' + ')} \n\n-----\n\n`;
                })
                .join(' | ')}`;
              setToolCalls((prev) => [...prev, toolCallMsg]);
            },
            callbackOnComplete: () => {
              const toolCallMsg = `on_complete called`;
              setToolCalls((prev) => [...prev, toolCallMsg]);
            },
          });
          break;
        case 'agentRunbookEditor':
          agentConfig = createSaiAgentRunbookEditorConfig({
            agent_context: {
              availableActionPackages: contextAgentAvailableActions ? contextAgentAvailableActions : [],
              availableMcpServers: contextAgentAvailableMcpServers ? contextAgentAvailableMcpServers : [],
              agentConversationStarter: contextAgentConversationStarter,
              agentQuestionGroups: contextAgentQuestionGroups ? contextAgentQuestionGroups : [],
              agentRunbook: contextAgentRunbook,
              agentName: contextAgentName,
              agentDescription: contextAgentDescription,
            },
            agent_architecture: {
              name: 'agent_platform.architectures.experimental_1',
              version: '0.0.1',
            },
            name: agentName,
            description: agentDescription,
            runbook: agentRunbook,
            platform_configs: [
              {
                kind: provider,
                openai_api_key: apiKey,
                models: {
                  [provider]: [model],
                },
              },
            ],
          });
          clientTools = SaiAgentEphemeral.configureSaiAgentRunbookEditorTools({
            callbackSetImprovements: (improvements: { original: string; improvement: string }[]) => {
              let tooolCall = (
                <div className="flex flex-col gap-2">
                  <h4>set_improvements called with improvements:</h4>
                  {improvements.map((improvement) => (
                    <div key={improvement.original} className="flex flex-col gap-1">
                      <div className="flex flex-col gap-1 bg-gray-100 p-2 rounded">
                        <div className="font-bold">Original:</div>
                        <div>{improvement.original}</div>
                      </div>
                      <div className="flex flex-col gap-1 bg-gray-100 p-2 rounded">
                        <div className="font-bold">Improvement:</div>
                        <div>{improvement.improvement}</div>
                      </div>
                    </div>
                  ))}
                </div>
              );
              setToolCalls((prev) => [...prev, tooolCall]);
            },
            callbackAddContentToRunbook: function (
              additions: { afterOriginalText: string; toAdd: string; asSibling: boolean }[],
            ): void {
              let tooolCall = (
                <div className="flex flex-col gap-2">
                  <h4>add_content_to_runbook called with additions:</h4>
                  {additions.map((addition) => (
                    <div key={addition.afterOriginalText} className="flex flex-col gap-1">
                      <div className="flex flex-col gap-1 bg-gray-100 p-2 rounded">
                        <div className="font-bold">After Original Text:</div>
                        <div>{addition.afterOriginalText}</div>
                      </div>
                      <div className="flex flex-col gap-1 bg-gray-100 p-2 rounded">
                        <div className="font-bold">To Add:</div>
                        <div>{addition.toAdd}</div>
                      </div>
                      <div className="flex flex-col gap-1 bg-gray-100 p-2 rounded">
                        <div className="font-bold">As Sibling:</div>
                        <div>{addition.asSibling ? 'Yes' : 'No'}</div>
                      </div>
                    </div>
                  ))}
                </div>
              );
              setToolCalls((prev) => [...prev, tooolCall]);
            },
            callbackRemoveContentFromRunbook: function (
              removals: { afterOriginalText: string; toRemove: string }[],
            ): void {
              let tooolCall = (
                <div className="flex flex-col gap-2">
                  <h4>remove_content_from_runbook called with removals:</h4>
                  {removals.map((removal) => (
                    <div key={removal.afterOriginalText} className="flex flex-col gap-1">
                      <div className="flex flex-col gap-1 bg-gray-100 p-2 rounded">
                        <div className="font-bold">After Original Text:</div>
                        <div>{removal.afterOriginalText}</div>
                      </div>
                      <div className="flex flex-col gap-1 bg-gray-100 p-2 rounded">
                        <div className="font-bold">To Remove:</div>
                        <div>{removal.toRemove}</div>
                      </div>
                    </div>
                  ))}
                </div>
              );
              setToolCalls((prev) => [...prev, tooolCall]);
            },
          });
          break;
      }

      let currentMessage = '';

      console.log('>>>> agentConfig', agentConfig);

      const stream = await client.createStream({
        agent: agentConfig,
        messages: [...messages, userMessage],
        client_tools: clientTools,
        handlers: {
          onOpen: () => {
            console.log('WebSocket connection opened');
          },
          onAgentReady: (event) => {
            console.log('Agent ready:', event);
          },
          onMessageContent: (event) => {
            // Extract text content from delta
            if (event.delta && event.delta.value) {
              const deltaValue = event.delta.value;
              // Check if the delta contains text content
              if (typeof deltaValue === 'string') {
                currentMessage += deltaValue;
              } else if (deltaValue.text) {
                currentMessage += deltaValue.text;
              }
            }
          },
          onMessageEnd: (event) => {
            console.log('>>>> onMessageEnd', event);
            const tempMessages: SaiAgentEphemeral.ThreadMessage[] = [
              ...messages,
              userMessage,
              event.data as SaiAgentEphemeral.ThreadMessage,
            ];
            setMessages(tempMessages);
            setStreaming(false);
          },
          onAgentError: (event) => {
            console.log('>>>> onAgentError', event);
            setError(event.error_message);
            setStreaming(false);
          },
          onClose: () => {
            console.log('WebSocket connection closed');
            setStreaming(false);
          },
        },
      });

      streamRef.current = stream;
    } catch (err) {
      console.error('>>>> error', err);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setInput('');
    }
  }, [
    input,
    streamRef,
    agentName,
    agentDescription,
    agentRunbook,
    provider,
    apiKey,
    baseUrl,
    messages,
    agentType,
    model,
    contextAgentName,
    contextAgentDescription,
    contextAgentRunbook,
    contextAgentAvailableActions,
    contextAgentAvailableMcpServers,
    contextAgentConversationStarter,
    contextAgentQuestionGroups,
  ]);

  const handleKeyPress = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    },
    [handleSendMessage],
  );

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    setContextAgentModel(model);
    setContextAgentModelProvider(provider);
  }, [model, provider]);

  useEffect(() => {
    switch (agentType) {
      case 'void': {
        setAgentName('');
        setAgentDescription('');
        setAgentRunbook('');
        break;
      }
      case 'generic': {
        const agent = new EphemeralGeneric({
          agentArchitecture: {
            name: 'agent_platform.architectures.experimental_1',
            version: '0.0.1',
          },
          platformConfig: {
            kind: provider,
            openai_api_key: apiKey,
            models: { [provider]: [model] },
          },
          promptClient: { baseUrl: baseUrl },
        });
        agent.setContext({ raw: agentRunbook });
        setAgentName(agent.agentPayload.name);
        setAgentDescription(agent.agentPayload.description);
        setAgentRunbook(agent.agentPayload.runbook || '');
        break;
      }
      case 'agentSetup': {
        const agent = new EphemeralAgentSetup({
          agentArchitecture: {
            name: 'agent_platform.architectures.experimental_1',
            version: '0.0.1',
          },
          platformConfig: {
            kind: provider,
            openai_api_key: apiKey,
            models: { [provider]: [model] },
          },
          promptClient: { baseUrl: baseUrl },
        });
        agent.setContext({ raw: agentRunbook });
        setAgentName(agent.agentPayload.name);
        setAgentDescription(agent.agentPayload.description);
        setAgentRunbook(agent.agentPayload.runbook || '');
        break;
      }
      case 'agentRunbookEditor': {
        const agent = new EphemeralAgentRunbookEditor({
          agentArchitecture: {
            name: 'agent_platform.architectures.experimental_1',
            version: '0.0.1',
          },
          platformConfig: {
            kind: provider,
            openai_api_key: apiKey,
            models: { [provider]: [model] },
          },
          promptClient: { baseUrl: baseUrl },
        });
        agent.setContext({
          agentModel: contextAgentModel,
          agentModelProvider: contextAgentModelProvider,
          agentName: contextAgentName,
          agentDescription: contextAgentDescription,
          agentRunbook: contextAgentRunbook,
          availableActionPackages: contextAgentAvailableActions ? contextAgentAvailableActions : [],
          availableMcpServers: contextAgentAvailableMcpServers ? contextAgentAvailableMcpServers : [],
          agentConversationStarter: contextAgentConversationStarter,
          agentQuestionGroups: contextAgentQuestionGroups ? contextAgentQuestionGroups : [],
        });
        setAgentName(agent.agentPayload.name);
        setAgentDescription(agent.agentPayload.description);
        setAgentRunbook(agent.agentPayload.runbook || '');
        break;
      }
    }
  }, [
    agentType,
    model,
    provider,
    contextAgentAvailableActions,
    contextAgentAvailableMcpServers,
    contextAgentConversationStarter,
    contextAgentQuestionGroups,
    contextAgentRunbook,
    contextAgentName,
    contextAgentDescription,
    contextAgentModel,
    contextAgentModelProvider,
  ]);

  useEffect(() => {
    scrollToBottom();
    messageInputRef.current?.focus();
  }, [messages]);

  return (
    <div className="mx-auto p-5 font-sans flex">
      <div className="flex flex-col gap-2.5 w-1/2 px-5">
        <h2 className="text-gray-800 mb-5 border-b-2 border-green-600 pb-2.5">Ephemeral Agent Chat Demo</h2>

        <div className="mb-4">
          <label className="block mb-1.5 font-semibold text-gray-600">Agent Name:</label>
          <input
            type="text"
            value={agentName}
            onChange={(e) => setAgentName(e.target.value)}
            placeholder="Enter agent name..."
            className="w-full p-2.5 border border-gray-300 rounded text-sm box-border focus:border-green-500"
          />
        </div>

        <div className="mb-4">
          <label className="block mb-1.5 font-semibold text-gray-600">Agent Description:</label>
          <input
            type="text"
            value={agentDescription}
            onChange={(e) => setAgentDescription(e.target.value)}
            placeholder="Enter agent description..."
            className="w-full p-2.5 border border-gray-300 rounded text-sm box-border focus:border-green-500"
          />
        </div>

        <div className="mb-4">
          <label className="block mb-1.5 font-semibold text-gray-600">Agent Runbook:</label>
          <textarea
            value={agentRunbook}
            onChange={(e) => setAgentRunbook(e.target.value)}
            rows={24}
            placeholder="Enter agent runbook..."
            className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
          />
        </div>
        {toolCalls.length > 0 && (
          <div className="bg-yellow-100 p-4 rounded border border-yellow-200 mb-4">
            <h4 className="mt-0 text-yellow-900">Tool Calls:</h4>
            {toolCalls.map((call, idx) => (
              <div key={idx} className="bg-white px-2 py-1.5 rounded-sm mb-1 text-xs font-mono">
                {call}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex-1 w-1/2 px-5">
        <div className="h-[800px] overflow-y-auto bg-white border border-gray-300 rounded p-4 mb-4">
          {messages.map((message, idx) => (
            <div
              key={idx}
              className={`mb-4 p-2.5 rounded-lg max-w-[80%] ${
                message.role === 'user' ? 'bg-green-600 text-white ml-auto' : 'bg-gray-100 text-gray-800'
              }`}
            >
              <div className="flex justify-between items-center mb-1.5 text-xs">
                <strong>{message.role === 'user' ? 'You' : agentName}</strong>
                <span className="opacity-70 text-[11px]">{message.created_at}</span>
              </div>
              <div className="whitespace-pre-wrap leading-normal">
                {message.content.map((content, contentIdx) => {
                  if (content.kind === 'text') {
                    return <span key={contentIdx}>{content.text}</span>;
                  }
                  if (content.kind === 'action') {
                    return (
                      <div key={contentIdx} className="mt-3 flex flex-wrap gap-2">
                        {content.actions.map((action, actionIdx) => (
                          <button
                            key={actionIdx}
                            onClick={() => {
                              setInput(action.value);
                              messageInputRef.current?.focus();
                            }}
                            className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 hover:border-green-500 transition-colors shadow-sm"
                          >
                            {action.label}
                          </button>
                        ))}
                      </div>
                    );
                  }
                  return null;
                })}
              </div>
            </div>
          ))}
          {streaming && (
            <div className="mb-4 p-2.5 rounded-lg max-w-[80%] bg-gray-100 text-gray-800">
              <div className="flex gap-1 p-2.5">
                <span className="w-2 h-2 rounded-full bg-gray-600 animate-typing"></span>
                <span className="w-2 h-2 rounded-full bg-gray-600 animate-typing [animation-delay:0.2s]"></span>
                <span className="w-2 h-2 rounded-full bg-gray-600 animate-typing [animation-delay:0.4s]"></span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="flex gap-2.5 items-end">
          <textarea
            ref={messageInputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            rows={2}
            disabled={streaming}
            className="flex-1 p-2.5 border border-gray-300 rounded text-sm resize-none disabled:opacity-60 focus:border-green-500"
          />
          <button
            onClick={handleSendMessage}
            disabled={!input.trim() || streaming}
            className="px-5 py-2.5 border-none rounded text-sm font-semibold cursor-pointer transition-all duration-200 bg-green-600 text-white hover:bg-green-700 disabled:opacity-60 disabled:cursor-not-allowed whitespace-nowrap"
          >
            Send
          </button>
        </div>

        {agentType === 'agentSetup' &&
          CONVERSATION_GUIDE.map((guide, idx) => (
            <button
              onClick={() => {
                setInput(guide);
              }}
              style={{ cursor: 'pointer', width: '100%', marginTop: '8px', textAlign: 'center' }}
            >
              <div
                key={idx}
                className="flex items-center justify-center text-center p-4 bg-green-200 rounded-lg hover:bg-green-300"
              >
                {guide}
              </div>
            </button>
          ))}
        {agentType === 'agentRunbookEditor' && (
          <>
            <div className="flex items-center justify-between mt-5 border-b-2 border-green-600 pb-2.5">
              <h2 className="text-gray-800 m-0">Context</h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    setContextAgentName('');
                    setContextAgentDescription('');
                    setContextAgentRunbook('');
                    setContextAgentAvailableActions([]);
                    setContextAgentAvailableMcpServers([]);
                    setContextAgentConversationStarter('');
                    setContextAgentQuestionGroups([]);
                    setContextAgentModel(model);
                    setContextAgentModelProvider(provider);
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
                    value={contextAgentName}
                    onChange={(e) => setContextAgentName(e.target.value)}
                    placeholder="Enter agent name..."
                    className="w-full p-2.5 border border-gray-300 rounded text-sm box-border focus:border-green-500"
                  />
                </div>

                <div className="mb-4">
                  <label className="block mb-1.5 text-gray-600">Agent Description:</label>
                  <textarea
                    value={contextAgentDescription}
                    onChange={(e) => setContextAgentDescription(e.target.value)}
                    rows={3}
                    placeholder="Enter agent description..."
                    className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
                  />
                </div>

                <div className="mb-4">
                  <label className="block mb-1.5 text-gray-600">Agent Runbook:</label>
                  <textarea
                    value={contextAgentRunbook}
                    onChange={(e) => setContextAgentRunbook(e.target.value)}
                    rows={3}
                    placeholder="Enter agent runbook..."
                    className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
                  />
                </div>

                <div className="mb-4">
                  <label className="block mb-1.5 text-gray-600">Agent Model:</label>
                  <input
                    type="text"
                    value={contextAgentModel}
                    onChange={(e) => setContextAgentModel(e.target.value)}
                    placeholder="e.g., gpt-4o, claude-3-5-sonnet, gpt-3.5-turbo"
                    className="w-full p-2.5 border border-gray-300 rounded text-sm box-border focus:border-green-500"
                  />
                </div>

                <div className="mb-4">
                  <label className="block mb-1.5 text-gray-600">Agent Model Provider:</label>
                  <input
                    type="text"
                    value={contextAgentModelProvider}
                    onChange={(e) => setContextAgentModelProvider(e.target.value)}
                    placeholder="e.g., openai, anthropic, azure"
                    className="w-full p-2.5 border border-gray-300 rounded text-sm box-border focus:border-green-500"
                  />
                </div>

                <div className="mb-4">
                  <label className="block mb-1.5 text-gray-600">Agent Available Actions:</label>
                  <textarea
                    value={contextAgentAvailableActions}
                    onChange={(e) => setContextAgentAvailableActions(JSON.parse(e.target.value))}
                    rows={3}
                    placeholder="Enter agent available actions. These should be an array of objects with the following properties: name, organization, version."
                    className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
                  />
                </div>
                <div className="mb-4">
                  <label className="block mb-1.5 text-gray-600">Agent Available MCP Servers:</label>
                  <textarea
                    value={contextAgentAvailableMcpServers}
                    onChange={(e) => setContextAgentAvailableMcpServers(JSON.parse(e.target.value))}
                    rows={3}
                    placeholder="Enter agent available MCP servers. These should be an array of MCP server objects."
                    className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
                  />
                </div>
                <div className="mb-4">
                  <label className="block mb-1.5 text-gray-600">Agent Conversation Starter:</label>
                  <textarea
                    value={contextAgentConversationStarter}
                    onChange={(e) => setContextAgentConversationStarter(e.target.value)}
                    rows={3}
                    placeholder="Enter agent conversation starter..."
                    className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
                  />
                </div>
                <div className="mb-4">
                  <label className="block mb-1.5 text-gray-600">Agent Question Groups:</label>
                  <textarea
                    value={contextAgentQuestionGroups}
                    onChange={(e) => setContextAgentQuestionGroups(JSON.parse(e.target.value))}
                    rows={3}
                    placeholder="Enter agent question groups..."
                    className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
                  />
                </div>

                <div className="bg-green-500 w-full h-[2px]" />
              </>
            )}
          </>
        )}
      </div>

      {error && (
        <div className="bg-red-100 text-red-900 p-4 rounded border border-red-200 my-5">
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  );
};
