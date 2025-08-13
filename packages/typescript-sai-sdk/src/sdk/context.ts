import { Context, ContextSchema } from './types';

// Type for context definition builder
interface ContextDefinitionBuilder {
  setSystemInstruction(instruction: string): ContextDefinitionBuilder;
  setTemperature(temperature: number): ContextDefinitionBuilder;
  setSeed(seed: number): ContextDefinitionBuilder;
  setMaxOutputTokens(maxTokens: number): ContextDefinitionBuilder;
  setStopSequences(sequences: string[]): ContextDefinitionBuilder;
  setTopP(topP: number): ContextDefinitionBuilder;
  build(): Context;
}

// Context builder class
class ContextBuilder implements ContextDefinitionBuilder {
  private context: Partial<Context> = {};

  setSystemInstruction(instruction: string): ContextDefinitionBuilder {
    this.context.system_instruction = instruction;
    return this;
  }

  setTemperature(temperature: number): ContextDefinitionBuilder {
    if (temperature < 0.0 || temperature > 1.0) {
      throw new Error('Temperature must be between 0.0 and 1.0');
    }
    this.context.temperature = temperature;
    return this;
  }

  setSeed(seed: number): ContextDefinitionBuilder {
    if (!Number.isInteger(seed)) {
      throw new Error('Seed must be an integer');
    }
    this.context.seed = seed;
    return this;
  }

  setMaxOutputTokens(maxTokens: number): ContextDefinitionBuilder {
    if (maxTokens <= 0) {
      throw new Error('Max output tokens must be positive');
    }
    this.context.max_output_tokens = maxTokens;
    return this;
  }

  setStopSequences(sequences: string[]): ContextDefinitionBuilder {
    this.context.stop_sequences = sequences;
    return this;
  }

  setTopP(topP: number): ContextDefinitionBuilder {
    if (topP < 0.0 || topP > 1.0) {
      throw new Error('Top P must be between 0.0 and 1.0');
    }
    this.context.top_p = topP;
    return this;
  }

  build(): Context {
    return ContextSchema.parse(this.context);
  }
}

export function createContext(): ContextDefinitionBuilder {
  return new ContextBuilder();
}

// Context preset functions
export function createDefaultContext(): ContextDefinitionBuilder {
  return createContext().setTemperature(0.0).setTopP(0.5).setMaxOutputTokens(256);
}

export function createConservativeContext(): ContextDefinitionBuilder {
  return createContext().setTemperature(0.2).setTopP(0.8).setMaxOutputTokens(1024);
}

export function createBalancedContext(): ContextDefinitionBuilder {
  return createContext().setTemperature(0.7).setTopP(0.9).setMaxOutputTokens(2048);
}

export function createCreativeContext(): ContextDefinitionBuilder {
  return createContext().setTemperature(0.9).setTopP(0.95).setMaxOutputTokens(3072).setSeed(42);
}

export type { ContextDefinitionBuilder };
