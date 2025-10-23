import React, { useCallback, useState } from 'react';
import { PromptEndpointClient } from '../../src/agent-prompt/client';
import { PromptResponse } from '../../src/agent-prompt/response';

export interface AgentPromptProps {
  apiKey: string;
  model?: string;
  provider?: 'openai' | 'azure' | 'ollama' | 'anthropic' | 'cortex' | 'bedrock';
}

export const AgentPromptDemo: React.FC<AgentPromptProps> = ({ apiKey, model = 'gpt-4o', provider = 'openai' }) => {
  const [prompt, setPrompt] = useState('What is the capital of France?');
  const [systemInstruction, setSystemInstruction] = useState('You are a helpful assistant.');
  const [response, setResponse] = useState<PromptResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const client = new PromptEndpointClient({
        baseUrl: '',
        verbose: true,
      });

      const result = await client.generate(
        {
          platform_config_raw: {
            kind: provider,
            openai_api_key: apiKey,
            models: {
              [provider]: [model],
            },
          },
          prompt: {
            system_instruction: systemInstruction,
            messages: [
              {
                role: 'user',
                content: [{ text: prompt }],
              },
            ],
            tools: [],
            tool_choice: 'auto',
          },
        },
        model,
      );

      setResponse(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [apiKey, model, provider, systemInstruction, prompt]);

  const handleStream = useCallback(async () => {
    setStreaming(true);
    setError(null);
    setStreamingText('');
    setResponse(null);

    try {
      const client = new PromptEndpointClient({
        baseUrl: '',
        verbose: true,
      });

      let accumulatedResponse: any = {};

      for await (const patch of client.stream(
        {
          platform_config_raw: {
            kind: provider,
            openai_api_key: apiKey,
            models: {
              [provider]: [model],
            },
          },
          prompt: {
            system_instruction: systemInstruction,
            messages: [
              {
                role: 'user',
                content: [{ text: prompt }],
              },
            ],
            tools: [],
            tool_choice: 'auto',
          },
        },
        model,
      )) {
        // Apply patch to accumulated response
        applyJsonPatch(accumulatedResponse, patch);

        // Extract text from content if available
        if (accumulatedResponse.content) {
          const textContent = accumulatedResponse.content
            .filter((c: any) => c.kind === 'text')
            .map((c: any) => c.text)
            .join('');
          setStreamingText(textContent);
        }
      }

      setResponse(accumulatedResponse as PromptResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setStreaming(false);
    }
  }, [apiKey, model, provider, systemInstruction, prompt]);

  const applyJsonPatch = (obj: any, operation: any) => {
    const pathParts = operation.path.split('/').filter((p: string) => p !== '');

    switch (operation.op) {
      case 'add':
      case 'replace':
        setNestedValue(obj, pathParts, operation.value);
        break;
      case 'concat_string':
        const currentString = getNestedValue(obj, pathParts) || '';
        setNestedValue(obj, pathParts, currentString + operation.value);
        break;
      case 'inc':
        const currentValue = getNestedValue(obj, pathParts) || 0;
        setNestedValue(obj, pathParts, currentValue + operation.value);
        break;
    }
  };

  const setNestedValue = (obj: any, pathParts: string[], value: any) => {
    let current = obj;
    for (let i = 0; i < pathParts.length - 1; i++) {
      const part = pathParts[i];
      const isArrayIndex = /^\d+$/.test(pathParts[i + 1]);
      if (!(part in current)) {
        current[part] = isArrayIndex ? [] : {};
      }
      current = current[part];
    }
    const lastPart = pathParts[pathParts.length - 1];
    current[lastPart] = value;
  };

  const getNestedValue = (obj: any, pathParts: string[]): any => {
    let current = obj;
    for (const part of pathParts) {
      if (current && typeof current === 'object' && part in current) {
        current = current[part];
      } else {
        return undefined;
      }
    }
    return current;
  };

  return (
    <div className="max-w-4xl mx-auto p-5 font-sans">
      <h2 className="text-gray-800 mb-5 border-b-2 border-green-600 pb-2.5">Agent Prompt Demo</h2>

      <div className="mb-4">
        <label className="block mb-1.5 font-semibold text-gray-600">Runbook:</label>
        <textarea
          value={systemInstruction}
          onChange={(e) => setSystemInstruction(e.target.value)}
          rows={2}
          placeholder="Enter system instruction..."
          className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
        />
      </div>

      <div className="mb-4">
        <label className="block mb-1.5 font-semibold text-gray-600">User Prompt:</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          placeholder="Enter your prompt..."
          className="w-full p-2.5 border border-gray-300 rounded text-sm box-border resize-y min-h-[60px] focus:border-green-500"
        />
      </div>

      <div className="flex gap-2.5 my-5">
        <button
          onClick={handleGenerate}
          disabled={loading || streaming}
          className="px-5 py-2.5 border-none rounded text-sm font-semibold cursor-pointer transition-all duration-200 bg-green-600 text-white hover:bg-green-700 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {loading ? 'Generating...' : 'Generate'}
        </button>
        <button
          onClick={handleStream}
          disabled={loading || streaming}
          className="px-5 py-2.5 border-none rounded text-sm font-semibold cursor-pointer transition-all duration-200 bg-gray-600 text-white hover:bg-gray-700 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {streaming ? 'Streaming...' : 'Stream'}
        </button>
      </div>

      {error && (
        <div className="bg-red-100 text-red-900 p-4 rounded border border-red-200 my-5">
          <div>
            <strong>Please make sure you are running Studio while testing the Sai SDK!</strong>
          </div>
          <strong>Error:</strong>
          <pre className="mt-2">{error}</pre>
        </div>
      )}

      {(streaming || streamingText) && (
        <div className="bg-gray-100 p-5 rounded border border-gray-300 my-5">
          <h3 className="mt-0 text-gray-800">Streaming Response:</h3>
          <div className="bg-white p-4 rounded border-l-4 border-green-600 whitespace-pre-wrap leading-relaxed min-h-[50px]">
            {streamingText}
          </div>
        </div>
      )}

      {response && (
        <div className="bg-gray-100 p-5 rounded border border-gray-300 my-5">
          <h3 className="mt-0 text-gray-800">Response:</h3>
          <div className="flex gap-5 mb-4 pb-4 border-b border-gray-300 text-sm">
            <span className="text-gray-600">
              <strong>Stop Reason:</strong> {response.stop_reason}
            </span>
            <span className="text-gray-600">
              <strong>Tokens Used:</strong> {response.usage?.total_tokens || 'N/A'}
            </span>
          </div>
          <div className="my-4">
            {response.content.map((content, idx) => (
              <div key={idx} className="mb-2.5">
                {content.kind === 'text' && (
                  <div className="bg-white p-4 rounded border-l-4 border-green-600 whitespace-pre-wrap leading-relaxed">
                    {content.text}
                  </div>
                )}
                {content.kind === 'tool_use' && (
                  <div className="bg-green-50 p-2.5 rounded border-l-4 border-green-800 text-sm">
                    <strong>Tool Call:</strong> {content.tool_name}
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
  );
};
