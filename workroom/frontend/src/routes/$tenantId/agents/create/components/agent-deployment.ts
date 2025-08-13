// Mock LLM providers (used by Step 1 and Step 2)
export const mockLLMProviders = [
  // OpenAI / ChatGPT
  { value: 'openai-gpt-5', label: 'ChatGPT 5', provider: 'OpenAI' },
  { value: 'openai-gpt-4.1', label: 'ChatGPT 4.1', provider: 'OpenAI' },
  { value: 'openai-gpt-4', label: 'ChatGPT 4', provider: 'OpenAI' },

  // Anthropic / Claude
  { value: 'anthropic-claude-4.1', label: 'Claude 4.1', provider: 'Anthropic' },
  { value: 'anthropic-claude-4', label: 'Claude 4', provider: 'Anthropic' },
  { value: 'anthropic-claude-3.5', label: 'Claude 3.5', provider: 'Anthropic' },

  // Google / Gemini (2.5 series)
  { value: 'google-gemini-2.5-pro', label: 'Gemini 2.5 Pro', provider: 'Google' },
  { value: 'google-gemini-2.5-flash', label: 'Gemini 2.5 Flash', provider: 'Google' },
];
