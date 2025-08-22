import {
  ContextDefinitionBuilder,
  createBalancedContext,
  createConservativeContext,
  createCreativeContext,
  createDefaultContext,
} from './context';
import { Context } from './types';

export type ScenarioContextType = 'default' | 'conservative' | 'balanced' | 'creative';

/**
 * Base interface for context instruction builders
 */
export interface IScenarioContextBuilder {
  /**
   * Add a section with a title and content
   */
  addSection(title: string, content: string | string[]): this;

  /**
   * Add raw objective without formatting
   */
  addObjectives(objectives: string | string[]): this;

  /**
   * Add context information
   */
  addContext(context: Record<string, any>): this;

  /**
   * Add steps
   */
  addSteps(steps: string | string[]): this;

  /**
   * Add guardrails/constraints
   */
  addGuardrails(guardrails: string | string[]): this;

  /**
   * Add example responses
   */
  addExampleResponses(responses: string | string[]): this;

  /**
   * Add a tool
   */
  buildContextInstructions(): string;

  /**
   * Build and return the Sai SDK creative context builder
   */
  buildContextBuilder(type: ScenarioContextType): ContextDefinitionBuilder;

  /**
   * Build and return the final built context
   */
  buildContext(type: ScenarioContextType): any;
}

/**
 * Generic context class for building system instructions for Sai SDK scenarios
 */
export class ScenarioContextBuilder implements IScenarioContextBuilder {
  private sections: string[] = [];
  private objectives: string[] = [];
  private steps: string[] = [];
  private contextData: Record<string, any> = {};
  private guardrails: string[] = [];
  private exampleResponses: string[] = [];
  /**
   * Add a section with a title and content
   */
  addSection(title: string, content: string | string[]): this {
    const contentArray = Array.isArray(content) ? content : [content];
    this.sections.push(`# ${title}`);
    this.sections.push(...contentArray);
    this.sections.push(''); // Add empty line for spacing
    return this;
  }

  /**
   * Add raw objectives without formatting
   */
  addObjectives(objectives: string | string[]): this {
    const objectiveArray = Array.isArray(objectives) ? objectives : [objectives];
    this.objectives.push(...objectiveArray);
    return this;
  }

  /**
   * Add context information
   */
  addContext(context: Record<string, any>): this {
    this.contextData = { ...this.contextData, ...context };
    return this;
  }

  /**
   * Add steps
   */
  addSteps(steps: string | string[]): this {
    const stepArray = Array.isArray(steps) ? steps : [steps];
    this.steps.push(...stepArray);
    return this;
  }

  /**
   * Add guardrails/constraints
   */
  addGuardrails(guardrails: string | string[]): this {
    const guardrailArray = Array.isArray(guardrails) ? guardrails : [guardrails];
    this.guardrails.push(...guardrailArray);
    return this;
  }

  /**
   * Add example responses
   */
  addExampleResponses(responses: string | string[]): this {
    const responseArray = Array.isArray(responses) ? responses : [responses];
    this.exampleResponses.push(...responseArray);
    return this;
  }

  /**
   * Build the final system instruction string
   */
  buildContextInstructions(): string {
    const parts: string[] = [];

    // Add raw objectives
    if (this.objectives.length > 0) {
      parts.push('# Objectives');
      parts.push(...this.objectives);
      parts.push(''); // Add empty line for spacing
    }

    // Add context data
    if (Object.keys(this.contextData).length > 0) {
      parts.push('# Context');
      Object.entries(this.contextData).forEach(([key, value]) => {
        const formattedKey = key.replace(/([A-Z])/g, ' $1').replace(/^./, (str) => str.toUpperCase());
        if (typeof value === 'object') {
          parts.push(`${formattedKey}: ${JSON.stringify(value)}`);
        } else {
          parts.push(`${formattedKey}: ${value}`);
        }
      });
      parts.push(''); // Add empty line for spacing
    }

    // Add steps
    if (this.steps.length > 0) {
      parts.push('# Steps');
      parts.push(...this.steps);
      parts.push(''); // Add empty line for spacing
    }

    // Add guardrails
    if (this.guardrails.length > 0) {
      parts.push('# Guardrails');
      parts.push(...this.guardrails);
      parts.push(''); // Add empty line for spacing
    }

    // Add example responses
    if (this.exampleResponses.length > 0) {
      parts.push('# Example Responses');
      parts.push(...this.exampleResponses);
      parts.push(''); // Add empty line for spacing
    }

    // Add sections
    if (this.sections.length > 0) {
      parts.push(...this.sections);
    }

    return parts.join('\n').trim();
  }

  /**
   * Build and return the Sai SDK creative context builder
   */
  buildContextBuilder(type: ScenarioContextType): ContextDefinitionBuilder {
    const systemInstruction = this.buildContextInstructions();

    switch (type) {
      case 'default':
        return createDefaultContext().setSystemInstruction(systemInstruction);
      case 'conservative':
        return createConservativeContext().setSystemInstruction(systemInstruction);
      case 'balanced':
        return createBalancedContext().setSystemInstruction(systemInstruction);
      case 'creative':
        return createCreativeContext().setSystemInstruction(systemInstruction);
      default:
        return createDefaultContext().setSystemInstruction(systemInstruction);
    }
  }

  /**
   * Build and return the final built context
   */
  buildContext(type: ScenarioContextType): Context {
    return this.buildContextBuilder(type).build();
  }

  /**
   * Reset the builder to start fresh
   */
  reset(): this {
    this.sections = [];
    this.objectives = [];
    this.steps = [];
    this.contextData = {};
    this.guardrails = [];
    this.exampleResponses = [];
    return this;
  }

  /**
   * Create a copy of the current builder
   */
  clone(): ScenarioContextBuilder {
    const cloned = new ScenarioContextBuilder();
    cloned.sections = [...this.sections];
    cloned.objectives = [...this.objectives];
    cloned.steps = [...this.steps];
    cloned.contextData = { ...this.contextData };
    cloned.guardrails = [...this.guardrails];
    cloned.exampleResponses = [...this.exampleResponses];
    return cloned;
  }
}
