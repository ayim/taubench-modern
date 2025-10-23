import { logger } from '../logger';
import {
  PromptRequest,
  PromptRequestSchema,
  PromptResponse,
  PromptResponseSchema,
  JsonPatchOperation,
  JsonPatchOperationSchema,
} from './index';

export interface PromptEndpointClientConfig {
  baseUrl: string;
  fetch?: typeof fetch;
  verbose?: boolean;
}

export class PromptEndpointClient {
  private baseUrl: string;
  private fetchFn: typeof fetch;
  private verbose: boolean;

  constructor(config: PromptEndpointClientConfig) {
    // If baseUrl is empty, use current origin (for proxy usage in browser)
    this.baseUrl = config.baseUrl
      ? config.baseUrl.replace(/\/$/, '') // Remove trailing slash
      : typeof window !== 'undefined'
        ? window.location.origin
        : '';
    this.fetchFn = config.fetch || fetch.bind(globalThis);
    this.verbose = config.verbose || false;
  }

  /**
   * Generate a prompt response synchronously
   */
  async generate(request: PromptRequest, model?: string): Promise<PromptResponse> {
    // Validate request
    const validatedRequest = PromptRequestSchema.parse(request);

    const url = new URL(`${this.baseUrl}/api/v2/prompts/generate`);
    if (model) {
      url.searchParams.set('model', model);
    }

    const response = await this.fetchFn(url.toString(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(validatedRequest),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const responseData = await response.json();

    // Validate response
    return PromptResponseSchema.parse(responseData);
  }

  /**
   * Stream a prompt response with Server-Sent Events
   */
  async *stream(request: PromptRequest, model?: string): AsyncGenerator<JsonPatchOperation, void, unknown> {
    // Validate request
    const validatedRequest = PromptRequestSchema.parse(request);

    const url = new URL(`${this.baseUrl}/api/v2/prompts/stream`);
    if (model) {
      url.searchParams.set('model', model);
    }

    const response = await this.fetchFn(url.toString(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(validatedRequest),
    });

    logger.infoIf(this.verbose, '[ScenarioBuilder.stream] got response:', response);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error('No response body for streaming');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete lines
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6); // Remove 'data: ' prefix
            if (dataStr.trim()) {
              try {
                const operation = JSON.parse(dataStr);
                // Validate the operation
                const validatedOperation = JsonPatchOperationSchema.parse(operation);
                yield validatedOperation;
              } catch (error) {
                logger.errorIf(this.verbose, 'Failed to parse streaming data:', dataStr, error);
              }
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  /**
   * Helper method to reconstruct a full response from streaming operations
   */
  async streamToResponse(request: PromptRequest, model?: string): Promise<PromptResponse> {
    let response: Partial<PromptResponse> = {};

    for await (const operation of this.stream(request, model)) {
      this.applyJsonPatch(response, operation);
    }

    // Validate the final response
    return PromptResponseSchema.parse(response);
  }

  /**
   * Apply a JSON Patch operation to an object
   */
  private applyJsonPatch(obj: any, operation: JsonPatchOperation): void {
    const pathParts = operation.path.split('/').filter((p) => p !== '');

    switch (operation.op) {
      case 'add':
      case 'replace':
        this.setNestedValue(obj, pathParts, operation.value);
        break;
      case 'remove':
        this.removeNestedValue(obj, pathParts);
        break;
      case 'inc':
        const currentValue = this.getNestedValue(obj, pathParts) || 0;
        this.setNestedValue(obj, pathParts, currentValue + operation.value);
        break;
      case 'concat_string':
        const currentString = this.getNestedValue(obj, pathParts) || '';
        this.setNestedValue(obj, pathParts, currentString + operation.value);
        break;
    }
  }

  // Set a nested value in an object
  private setNestedValue(obj: any, pathParts: string[], value: any): void {
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
  }

  // Get a nested value from an object
  private getNestedValue(obj: any, pathParts: string[]): any {
    let current = obj;

    for (const part of pathParts) {
      if (current && typeof current === 'object' && part in current) {
        current = current[part];
      } else {
        return undefined;
      }
    }

    return current;
  }

  // Remove a nested value from an object
  private removeNestedValue(obj: any, pathParts: string[]): void {
    if (pathParts.length === 0) return;

    let current = obj;

    for (let i = 0; i < pathParts.length - 1; i++) {
      const part = pathParts[i];
      if (!(part in current)) return;
      current = current[part];
    }

    const lastPart = pathParts[pathParts.length - 1];
    if (Array.isArray(current)) {
      current.splice(parseInt(lastPart), 1);
    } else {
      delete current[lastPart];
    }
  }
}
