import { ScenarioTool, ScenarioToolSchema } from './types';
import { JsonSchemaProperty, ToolCategory } from '../tools';

// Type for tool definition builder
interface ToolDefinitionBuilder {
  // Set the name and description of the tool
  setName(name: string): ToolDefinitionBuilder;
  // Set the description of the tool
  setDescription(description: string): ToolDefinitionBuilder;
  // Set the callback function for the tool
  setCallback(callback: (input: any) => any): ToolDefinitionBuilder;
  // Set the category of the tool
  setCategory(category: ToolCategory): ToolDefinitionBuilder;

  // Add properties to the tool input schema
  addProperty(name: string, property: JsonSchemaProperty): ToolDefinitionBuilder;
  addStringProperty(name: string, description?: string): ToolDefinitionBuilder;
  addNumberProperty(name: string, description?: string): ToolDefinitionBuilder;
  addBooleanProperty(name: string, description?: string): ToolDefinitionBuilder;
  addArrayProperty(name: string, itemType: JsonSchemaProperty, description?: string): ToolDefinitionBuilder;
  addObjectProperty(
    name: string,
    properties: Record<string, JsonSchemaProperty>,
    requiredFields?: string[],
    description?: string,
  ): ToolDefinitionBuilder;
  addEnumProperty(name: string, values: any[], description?: string): ToolDefinitionBuilder;

  // Set required fields for the tool input schema
  setRequired(fields: string[]): ToolDefinitionBuilder;
  addRequired(field: string): ToolDefinitionBuilder;

  // Build the tool
  build(): ScenarioTool;
}

// Tool definition builder class
class ToolBuilder implements ToolDefinitionBuilder {
  private tool: Partial<ScenarioTool> = {
    input_schema: {
      type: 'object',
      properties: {},
      required: [],
    },
    category: 'client-info-tool',
  };

  // Set the name and description of the tool
  setName(name: string): ToolDefinitionBuilder {
    this.tool.name = name;
    return this;
  }

  // Set the description of the tool
  setDescription(description: string): ToolDefinitionBuilder {
    this.tool.description = description;
    return this;
  }

  // Set the callback function for the tool
  setCallback(callback: (input: any) => any): ToolDefinitionBuilder {
    this.tool.callback = callback;
    return this;
  }

  // Set the category of the tool
  setCategory(category: ToolCategory): ToolDefinitionBuilder {
    this.tool.category = category;
    return this;
  }

  // Add properties to the tool input schema
  addProperty(name: string, property: JsonSchemaProperty): ToolDefinitionBuilder {
    if (!this.tool.input_schema) {
      this.tool.input_schema = { type: 'object', properties: {} };
    }
    this.tool.input_schema.properties![name] = property;
    return this;
  }

  addStringProperty(name: string, description?: string): ToolDefinitionBuilder {
    const property: JsonSchemaProperty = {
      type: 'string',
      ...(description && { description }),
    };
    this.addProperty(name, property);
    return this;
  }

  addNumberProperty(name: string, description?: string): ToolDefinitionBuilder {
    const property: JsonSchemaProperty = {
      type: 'number',
      ...(description && { description }),
    };
    this.addProperty(name, property);
    return this;
  }

  addBooleanProperty(name: string, description?: string): ToolDefinitionBuilder {
    const property: JsonSchemaProperty = {
      type: 'boolean',
      ...(description && { description }),
    };
    this.addProperty(name, property);
    return this;
  }

  addArrayProperty(name: string, itemType: JsonSchemaProperty, description?: string): ToolDefinitionBuilder {
    const property: JsonSchemaProperty = {
      type: 'array',
      items: itemType,
      ...(description && { description }),
    };
    this.addProperty(name, property);
    return this;
  }

  addObjectProperty(
    name: string,
    properties: Record<string, JsonSchemaProperty>,
    requiredFields?: string[],
    description?: string,
  ): ToolDefinitionBuilder {
    const property: JsonSchemaProperty = {
      type: 'object',
      properties,
      ...(requiredFields && { required: requiredFields }),
      ...(description && { description }),
    };
    this.addProperty(name, property);
    return this;
  }

  addEnumProperty(name: string, values: any[], description?: string): ToolDefinitionBuilder {
    const property: JsonSchemaProperty = {
      type: 'string',
      enum: values,
      ...(description && { description }),
    };
    this.addProperty(name, property);
    return this;
  }

  // Set required fields for the tool input schema
  setRequired(fields: string[]): ToolDefinitionBuilder {
    if (!this.tool.input_schema) {
      this.tool.input_schema = { type: 'object', properties: {} };
    }
    this.tool.input_schema.required = fields;
    return this;
  }

  addRequired(field: string): ToolDefinitionBuilder {
    if (!this.tool.input_schema) {
      this.tool.input_schema = { type: 'object', properties: {} };
    }
    if (!this.tool.input_schema.required) {
      this.tool.input_schema.required = [];
    }
    if (!this.tool.input_schema.required.includes(field)) {
      this.tool.input_schema.required.push(field);
    }
    return this;
  }

  // Build the tool
  build(): ScenarioTool {
    if (!this.tool.name || !this.tool.description) {
      throw new Error('Tool name and description are required');
    }
    return ScenarioToolSchema.parse(this.tool);
  }
}

// Factory functions for creating tool builders
export function createSimpleTool(name: string, description: string): ToolDefinitionBuilder {
  const builder = new ToolBuilder();
  builder.setName(name);
  builder.setDescription(description);
  builder.setCallback(() => {});
  builder.setCategory('client-info-tool');
  return builder;
}

// Validation functions
export function validateTool(tool: unknown): tool is ScenarioTool {
  try {
    ScenarioToolSchema.parse(tool);
    return true;
  } catch {
    return false;
  }
}

// Export types for external use
export type { ToolDefinitionBuilder };
