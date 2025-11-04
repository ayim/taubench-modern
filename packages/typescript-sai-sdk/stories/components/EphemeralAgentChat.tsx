import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  EphemeralAgentClient,
  createBasicAgentConfig,
  createUserThreadMessage,
  SaiAgentEphemeral,
  createSaiAgentSetupConfig,
} from '../../src/index';
import type { ToolDefinitionPayload } from '../../src/agent-ephemeral/types';
import { AGENT_SETUP_CONTEXT } from '../helpers/context';
import { createSaiGenericAgentConfig } from '../../src/agent-ephemeral/agents/generic';

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
  agentType?: 'void' | 'generic' | 'agentSetup';
}

export const EphemeralAgentChat: React.FC<EphemeralAgentChatProps> = ({
  baseUrl,
  apiKey,
  model = 'gpt-4o',
  provider = 'openai',
  agentType = 'void',
}) => {
  const [messages, setMessages] = useState<SaiAgentEphemeral.ThreadMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentName, setAgentName] = useState(AGENT_SETUP_CONTEXT.agentName);
  const [agentDescription, setAgentDescription] = useState(AGENT_SETUP_CONTEXT.agentDescription);
  const [agentRunbook, setAgentRunbook] = useState(AGENT_SETUP_CONTEXT.agentRunbook);
  const [toolCalls, setToolCalls] = useState<string[]>([]);
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
    switch (agentType) {
      case 'void': {
        setAgentName('');
        setAgentDescription('');
        setAgentRunbook('');
        break;
      }
      case 'generic': {
        const agentConfig = createSaiGenericAgentConfig({
          agent_architecture: {
            name: 'agent_platform.architectures.experimental_1',
            version: '0.0.1',
          },
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
        setAgentName(agentConfig.name);
        setAgentDescription(agentConfig.description);
        setAgentRunbook(agentConfig.runbook || '');
        break;
      }
      case 'agentSetup': {
        const agentConfig = createSaiAgentSetupConfig({
          agent_architecture: {
            name: 'agent_platform.architectures.experimental_1',
            version: '0.0.1',
          },
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
        setAgentName(agentConfig.name);
        setAgentDescription(agentConfig.description);
        setAgentRunbook(agentConfig.runbook || '');
        break;
      }
    }
  }, [agentType, model]);

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
                {message.content.map((content) => {
                  if (content.kind === 'text') {
                    return content.text;
                  }
                  return '';
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

        {CONVERSATION_GUIDE.map((guide, idx) => (
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
      </div>

      {error && (
        <div className="bg-red-100 text-red-900 p-4 rounded border border-red-200 my-5">
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  );
};
