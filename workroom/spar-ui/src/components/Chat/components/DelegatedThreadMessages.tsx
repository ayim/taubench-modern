import { FC, Fragment } from 'react';
import { ThreadToolUsageContent, components } from '@sema4ai/agent-server-interface';
import { Box, Chat } from '@sema4ai/components';
import { ToolCall } from './ToolCall';
import { markdownRules } from './markdown';
import { shouldIgnoreToolCall } from './renderer/Item';

type SQLGenerationDetailsResponse = components['schemas']['SQLGenerationDetailsResponse'];
type ThreadAgentMessage = components['schemas']['ThreadAgentMessage'];

type Props = {
  content: ThreadToolUsageContent;
};

const isSQLGenerationDetailsResponse = (metadata: unknown): metadata is SQLGenerationDetailsResponse => {
  if (!metadata || typeof metadata !== 'object') return false;
  const m = metadata as Record<string, unknown>;
  return 'intent' in m && 'semantic_data_model_name' in m && 'agent_messages' in m && Array.isArray(m.agent_messages);
};

// Create a stable key from content (first 100 chars of stringified content)
const createContentKey = (content: unknown): string => {
  const str = JSON.stringify(content);
  return str.substring(0, 100).replace(/[^a-zA-Z0-9]/g, '_');
};

export const DelegatedThreadMessages: FC<Props> = ({ content }) => {
  // Extract SQL generation details from metadata
  const delegatedThread = content.metadata?.execution as Record<string, unknown> | undefined;
  const details = delegatedThread?.sql_generation_details;

  // Validate and type-check the details against SQLGenerationDetailsAPI schema
  if (!isSQLGenerationDetailsResponse(details)) {
    return null;
  }

  return (
    <Chat.Action title="SQL generation details">
      <Box display="flex" flexDirection="column" gap="$8">
        {details.agent_messages.map((message: ThreadAgentMessage) => {
          const messageKey = createContentKey(message);
          return (
            <Fragment key={messageKey}>
              {message.content.map((contentItem) => {
                const contentKey = createContentKey(contentItem);

                // Render agent text messages
                if (contentItem.kind === 'text' && 'text' in contentItem && contentItem.text) {
                  return (
                    <Chat.Markdown
                      key={`${messageKey}-${contentKey}`}
                      messageId={messageKey}
                      streaming={false}
                      parserRules={markdownRules}
                    >
                      {contentItem.text}
                    </Chat.Markdown>
                  );
                }

                // Render tool calls
                if (contentItem.kind === 'tool_call' && 'name' in contentItem) {
                  // Skip internal tool calls that don't bring value to the user
                  if (shouldIgnoreToolCall(contentItem.name ?? '')) {
                    return null;
                  }

                  const toolCallContent: ThreadToolUsageContent = {
                    kind: 'tool_call',
                    content_id: contentItem.content_id ?? contentKey,
                    name: contentItem.name ?? '',
                    tool_call_id: 'tool_call_id' in contentItem ? (contentItem.tool_call_id ?? '') : '',
                    arguments_raw: 'arguments_raw' in contentItem ? (contentItem.arguments_raw ?? '') : '',
                    result: 'result' in contentItem ? (contentItem.result ?? null) : null,
                    error: 'error' in contentItem ? (contentItem.error ?? null) : null,
                    status:
                      'status' in contentItem
                        ? ((contentItem.status as ThreadToolUsageContent['status']) ?? 'pending')
                        : 'pending',
                    complete: contentItem.complete ?? true,
                    sub_type:
                      'sub_type' in contentItem
                        ? ((contentItem.sub_type as ThreadToolUsageContent['sub_type']) ?? 'unknown')
                        : 'unknown',
                    action_server_run_id:
                      'action_server_run_id' in contentItem ? (contentItem.action_server_run_id ?? null) : null,
                    metadata:
                      'metadata' in contentItem && contentItem.metadata
                        ? (contentItem.metadata as { [key: string]: unknown })
                        : undefined,
                  };

                  return <ToolCall key={`${messageKey}-${contentKey}`} content={toolCallContent} />;
                }

                return null;
              })}
            </Fragment>
          );
        })}
      </Box>
    </Chat.Action>
  );
};
