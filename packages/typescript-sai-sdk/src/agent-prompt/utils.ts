import {
  Message,
  AllMessage,
  MessageContent,
  TextContent,
  ImageContent,
  ToolUseContent,
  ToolResultContent,
  Tool,
  ToolChoice,
  PlatformConfig,
  PromptRequest,
  PromptSchema,
  ConversationHistorySpecialMessage,
  DocumentsSpecialMessage,
  MemoriesSpecialMessage,
} from './index';

/**
 * Create a text content object
 */
export function createTextContent(text: string): TextContent {
  return { text };
}

/**
 * Create an image content object from base64 data
 */
export function createImageContent(
  base64Data: string,
  mimeType: string,
  detail: 'low_res' | 'high_res' = 'high_res',
): ImageContent {
  return {
    kind: 'image',
    value: base64Data,
    mime_type: mimeType,
    sub_type: 'base64',
    detail,
  };
}

/**
 * Create a tool use content object
 */
export function createToolUseContent(
  toolName: string,
  toolCallId: string,
  toolInput: Record<string, any>,
): ToolUseContent {
  return {
    kind: 'tool_use',
    tool_name: toolName,
    tool_call_id: toolCallId,
    tool_input_raw: JSON.stringify(toolInput),
  };
}

/**
 * Create a tool result content object
 */
export function createToolResultContent(toolName: string, toolCallId: string, result: string): ToolResultContent {
  return {
    kind: 'tool_result',
    tool_name: toolName,
    tool_call_id: toolCallId,
    content: [{ text: result }],
  };
}

/**
 * Create a user message
 */
export function createUserMessage(content: MessageContent[]): Message {
  return {
    role: 'user',
    content,
  };
}

/**
 * Create an agent message
 */
export function createAgentMessage(content: MessageContent[]): Message {
  return {
    role: 'agent',
    content,
  };
}

/**
 * Create a simple text user message
 */
export function createTextUserMessage(text: string): Message {
  return createUserMessage([createTextContent(text)]);
}

/**
 * Create a simple text agent message
 */
export function createTextAgentMessage(text: string): Message {
  return createAgentMessage([{ kind: 'text', text }]);
}

/**
 * Create a tool definition
 */
export function createTool(
  name: string,
  description: string,
  properties: Record<string, any>,
  required: string[] = [],
): Tool {
  return {
    name,
    description,
    input_schema: {
      type: 'object',
      properties,
      required,
    },
  };
}

/**
 * Create an OpenAI platform config
 */
export function createOpenAIConfig(apiKey: string): PlatformConfig {
  return {
    kind: 'openai',
    openai_api_key: apiKey,
  };
}

/**
 * Create a Google platform config
 */
export function createGoogleConfig(apiKey: string): PlatformConfig {
  return {
    kind: 'google',
    google_api_key: apiKey,
  };
}

/**
 * Create a Groq platform config
 */
export function createGroqConfig(apiKey: string): PlatformConfig {
  return {
    kind: 'groq',
    groq_api_key: apiKey,
  };
}

/**
 * Create a Bedrock platform config
 */
export function createBedrockConfig(accessKeyId: string, secretAccessKey: string, region: string): PlatformConfig {
  return {
    kind: 'bedrock',
    aws_access_key_id: accessKeyId,
    aws_secret_access_key: secretAccessKey,
    region_name: region,
  };
}

/**
 * Create a conversation history special message
 */
export function createConversationHistoryMessage(numTurns?: number): ConversationHistorySpecialMessage {
  return {
    role: '$conversation_history',
    ...(numTurns !== undefined && { num_turns: numTurns }),
  };
}

/**
 * Create a documents special message
 */
export function createDocumentsMessage(documentIds?: string[]): DocumentsSpecialMessage {
  return {
    role: '$documents',
    ...(documentIds !== undefined && { document_ids: documentIds }),
  };
}

/**
 * Create a memories special message
 */
export function createMemoriesMessage(memoryLimit?: number): MemoriesSpecialMessage {
  return {
    role: '$memories',
    ...(memoryLimit !== undefined && { memory_limit: memoryLimit }),
  };
}

/**
 * Create a complete prompt request with all available options
 *
 * @param platformConfig - The platform configuration (OpenAI, Google, Groq, or Bedrock)
 * @param messages - Array of messages including regular and special messages
 * @param tools - Array of tool definitions available to the model
 * @param options - Optional configuration for the prompt
 * @param options.systemInstruction - Initial instruction that defines the AI's behavior
 * @param options.toolChoice - Tool selection strategy: 'auto', 'any', or specific tool name
 * @param options.temperature - Sampling temperature (0.0-1.0, where 0.0 is deterministic)
 * @param options.seed - Seed for deterministic responses
 * @param options.maxOutputTokens - Maximum number of tokens in the response
 * @param options.stopSequences - Array of sequences that will stop generation
 * @param options.topP - Nucleus sampling parameter (0.0-1.0)
 * @returns A validated PromptRequest object
 * @throws {Error} If the prompt configuration is invalid
 */
export function createPromptRequest(
  platformConfig: PlatformConfig,
  messages: AllMessage[],
  tools: Tool[] = [],
  options: {
    systemInstruction?: string;
    toolChoice?: ToolChoice;
    temperature?: number;
    seed?: number;
    maxOutputTokens?: number;
    stopSequences?: string[];
    topP?: number;
  } = {},
): PromptRequest {
  // Create the prompt object
  const prompt = {
    ...(options.systemInstruction !== undefined && {
      system_instruction: options.systemInstruction,
    }),
    messages,
    tools,
    tool_choice: options.toolChoice ?? 'auto',
    ...(options.temperature !== undefined && { temperature: options.temperature }),
    ...(options.seed !== undefined && { seed: options.seed }),
    ...(options.maxOutputTokens !== undefined && {
      max_output_tokens: options.maxOutputTokens,
    }),
    ...(options.stopSequences !== undefined && {
      stop_sequences: options.stopSequences,
    }),
    ...(options.topP !== undefined && { top_p: options.topP }),
  };

  // Validate the prompt against the schema
  const validatedPrompt = PromptSchema.parse(prompt);

  return {
    platform_config_raw: platformConfig,
    prompt: validatedPrompt,
  };
}

/**
 * Generate a random tool call ID
 */
export function generateToolCallId(): string {
  return crypto.randomUUID();
}

/**
 * Helper to convert a file to base64 (for browser environments)
 */
export async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Remove the data URL prefix (e.g., "data:image/jpeg;base64,")
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/**
 * Helper to convert base64 string to File (for browser environments)
 */
export function base64ToFile(base64: string, filename: string, mimeType: string): File {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);

  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }

  const byteArray = new Uint8Array(byteNumbers);
  return new File([byteArray], filename, { type: mimeType });
}
