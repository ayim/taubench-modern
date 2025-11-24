import { createBasicAgentConfig } from '../client';
import { ToolDefinitionPayload, UpsertAgentPayload } from '../types';
import { createSimpleTool } from '../../sdk/tools';
import { SAI_AGENT_RUNBOOK_EDITOR_RUNBOOK } from './agent-runbook-editor-runbooks/the-runbook';
import { AgentConfigurationOptions } from './types';
import { ContextBuilder } from '../../context-builder';

const SAI_AGENT_RUNBOOK_EDITOR_NAME = 'sai-sdk-agent-runbook-editor';
const SAI_AGENT_RUNBOOK_EDITOR_DESCRIPTION = 'Sai Expert Agent Runbook Editor';

type AgentRunbookEditorTools = {
  callbackSetImprovements: (improvements: { original: string; improvement: string }[]) => void;
  callbackAddContentToRunbook: (additions: { afterOriginalText: string; toAdd: string; asSibling: boolean }[]) => void;
  callbackRemoveContentFromRunbook: (removals: { afterOriginalText: string; toRemove: string }[]) => void;
};

/**
 * Utility function to create a basic ephemeral agent configuration
 */
export function createSaiAgentRunbookEditorConfig(options: AgentConfigurationOptions): UpsertAgentPayload {
  const agentContext = options.agent_context ?? {};
  const runbook = new ContextBuilder()
    .setRawSystemInstructions(SAI_AGENT_RUNBOOK_EDITOR_RUNBOOK)
    .addContext(agentContext)
    .buildContext('creative').system_instruction;

  // Create and return the agent config
  return createBasicAgentConfig({
    name: options.name || SAI_AGENT_RUNBOOK_EDITOR_NAME + Date.now().toString(),
    description: options.description || SAI_AGENT_RUNBOOK_EDITOR_DESCRIPTION,
    runbook: options.runbook || runbook || SAI_AGENT_RUNBOOK_EDITOR_RUNBOOK,
    platform_configs: options.platform_configs,
    agent_id: options.agent_id,
    agent_architecture: options.agent_architecture,
  });
}

/**
 * Utility function to configure the tools for the agent setup
 */
export function configureSaiAgentRunbookEditorTools(
  agentRunbookEditorTools: AgentRunbookEditorTools,
): ToolDefinitionPayload[] {
  const tools: ToolDefinitionPayload[] = [];

  // Set the description of the agent
  const setImprovementsTool: ToolDefinitionPayload = createSimpleTool(
    'set_improvements_to_runbook',
    [
      'Set the improvements to the runbook.',
      'The original text must be EXACTLY ONE LINE from the runbook - no multiple lines, no line breaks.',
      'The original text must match character-for-character from the runbook.',
      'The improvement must be a valid Markdown string.',
      'To improve multiple lines, add multiple entries to the improvements array.',
    ].join('\n'),
  )
    .addArrayProperty('improvements', {
      type: 'object',
      properties: {
        original: { type: 'string' },
        improvement: { type: 'string' },
      },
    })
    .setRequired(['improvements'])
    .setCallback((i) => {
      agentRunbookEditorTools.callbackSetImprovements(i.improvements);
    })
    .setCategory('client-info-tool')
    .build();
  tools.push(setImprovementsTool);

  const addContentToRunbookTool: ToolDefinitionPayload = createSimpleTool(
    'add_content_to_runbook',
    [
      'Add content to the runbook.',
      'The afterOriginalText must be EXACTLY ONE LINE from the runbook - no multiple lines, no line breaks.',
      'The afterOriginalText must match character-for-character from the runbook.',
      'The toAdd is the text to add after the original text. It must be a valid Markdown string.',
      'The asSibling is a boolean indicating whether the text should be added as a sibling of the original text.',
      'To add multiple items, add multiple entries to the additions array.',
    ].join('\n'),
  )
    .addArrayProperty('additions', {
      type: 'object',
      properties: {
        afterOriginalText: { type: 'string' },
        toAdd: { type: 'string' },
        asSibling: { type: 'boolean' },
      },
    })
    .addRequired('additions')
    .setCallback((i) => {
      agentRunbookEditorTools.callbackAddContentToRunbook(i.additions);
    })
    .setCategory('client-info-tool')
    .build();
  tools.push(addContentToRunbookTool);

  const removeContentFromRunbookTool: ToolDefinitionPayload = createSimpleTool(
    'remove_content_from_runbook',
    [
      'Remove content from the runbook.',
      'The afterOriginalText must be EXACTLY ONE LINE from the runbook - no multiple lines, no line breaks.',
      'The afterOriginalText must match character-for-character from the runbook.',
      'The toRemove must be EXACTLY ONE LINE from the runbook - no multiple lines, no line breaks.',
      'The toRemove must match character-for-character from the runbook.',
      'To remove multiple lines, add multiple entries to the removals array.',
    ].join('\n'),
  )
    .addArrayProperty('removals', {
      type: 'object',
      properties: {
        afterOriginalText: { type: 'string' },
        toRemove: { type: 'string' },
      },
    })
    .addRequired('removals')
    .setCallback((i) => {
      agentRunbookEditorTools.callbackRemoveContentFromRunbook(i.removals);
    })
    .setCategory('client-info-tool')
    .build();
  tools.push(removeContentFromRunbookTool);
  return tools;
}
