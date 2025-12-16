import { ThreadMessage } from '@sema4ai/agent-server-interface';
import { formatDate } from '@sema4ai/components/utils';
import { shouldIgnoreToolCall } from '../components/renderer/Item';
import { AgentErrorStreamPayload } from '../../../lib/AgentServerTypes';
import { snakeCaseToTitleCase } from '../../../common/helpers';
import { getGroupedMessageContent } from '../components/renderer/Message';
import { getActionGroupStateDetails } from '../components/ToolCall';
import { formatThoughtTitle } from '../components/renderer/Thinking';
import { safeParseJson } from '../../../lib/utils';

type ThreadMessageContent = ThreadMessage['content'][number];

const EMOJI_MAP: {
  role: Record<ThreadMessage['role'], string>;
  kind: Record<ThreadMessageContent['kind'], string>;
  tool_call_state: Record<'in_progress' | 'done' | 'failed', string>;
  status: Record<'error', string>;
} = {
  role: {
    user: '👤',
    agent: '🤖',
  },
  kind: {
    attachment: '📎',
    tool_call: '🔧',
    vega_chart: '📊',
    text: '',
    quick_actions: '',
    thought: '',
  },
  tool_call_state: {
    in_progress: '▶️',
    done: '✅',
    failed: '❌',
  },
  status: {
    error: '⚠️',
  },
};

const STATUS_EMOJI_MAP: Record<Extract<ThreadMessageContent, { kind: 'tool_call' }>['status'], string> = {
  pending: EMOJI_MAP.tool_call_state.in_progress,
  running: EMOJI_MAP.tool_call_state.in_progress,
  streaming: EMOJI_MAP.tool_call_state.in_progress,
  finished: EMOJI_MAP.tool_call_state.done,
  failed: EMOJI_MAP.tool_call_state.failed,
};

const parseContentItem = (item: ThreadMessage['content'][number], platform: string | undefined): string => {
  switch (item.kind) {
    case 'text':
      return item.text;

    case 'thought': {
      if (!item.thought || item.thought.trim() === '') {
        return '';
      }
      const title = formatThoughtTitle({ text: item.thought, complete: item.complete, platform });
      const quotedThought = item.thought
        .split('\n')
        .map((line) => `> ${line}`)
        .join('\n');
      return `**${title}**\n${quotedThought}\n`;
    }

    case 'tool_call': {
      if (shouldIgnoreToolCall(item.name)) {
        return '';
      }

      let markdown = `### ${STATUS_EMOJI_MAP[item.status]} ${snakeCaseToTitleCase(item.name)}\n\n`;

      const isError = item.status === 'failed';

      const input = item.arguments_raw;
      const output = isError ? (item.error ?? item.result) : item.result;

      const parsedInput = safeParseJson(input);
      const parsedOutput = safeParseJson(output);

      if (!parsedOutput && Boolean(parsedInput)) {
        markdown += `**Result**:\n\`\`\`json\n${JSON.stringify({ Input: parsedInput }, null, 2)}\n\`\`\`\n\n`;
      }

      if (Boolean(parsedOutput) && Boolean(parsedInput)) {
        markdown += `**Result**:\n\`\`\`json\n${JSON.stringify({ Input: parsedInput, Output: parsedOutput }, null, 2)}\n\`\`\`\n\n`;
      }

      if (item.error) {
        markdown += `**Error**: ${EMOJI_MAP.status.error} ${item.error}\n\n`;
      }

      return markdown;
    }

    case 'attachment': {
      let markdown = `### ${EMOJI_MAP.kind.attachment} Attachment: ${item.name}\n\n`;

      if (item.description) {
        markdown += `${item.description}\n\n`;
      }

      markdown += `**Type**: ${item.mime_type}\n\n`;

      if (item.uri) {
        markdown += `**URI**: ${item.uri}\n\n`;
      }

      return markdown;
    }

    case 'vega_chart': {
      return `### ${EMOJI_MAP.kind.vega_chart} Chart\n\n\`\`\`json\n${JSON.stringify(item, null, 2)}\n\`\`\`\n\n`;
    }

    case 'quick_actions': {
      return '';
    }

    default:
      return '';
  }
};

const threadMessageMakrdown = (message: ThreadMessage): string => {
  const role = message.role === 'user' ? `${EMOJI_MAP.role.user} User` : `${EMOJI_MAP.role.agent} Agent`;
  const timestamp = formatDate(new Date(message.created_at), { preset: 'datetime' });

  const messageMetadataPlatform = message.agent_metadata?.platform;
  const platform = typeof messageMetadataPlatform === 'string' ? messageMetadataPlatform : undefined;

  let markdown = `\n---\n\n## ${role} _(${timestamp})_`;
  markdown += '\n\n';

  const groupedContent = getGroupedMessageContent(message.content ?? [], message.complete);
  const renderedMessageContent = groupedContent.map((processedContent) => {
    if (Array.isArray(processedContent)) {
      const groupDetails = getActionGroupStateDetails({
        messageContent: processedContent,
        messageComplete: message.complete,
        platform,
      });

      let groupedMarkdownContent = `### ${EMOJI_MAP.tool_call_state[groupDetails.state]} ${groupDetails.title}\n\n`;
      groupedMarkdownContent += processedContent
        .map((processedContentItem) => parseContentItem(processedContentItem, platform))
        .filter((content) => content.trim() !== '')
        .join('\n');
      return groupedMarkdownContent;
    }

    return parseContentItem(processedContent, platform);
  });

  markdown += renderedMessageContent.filter((content) => content.trim() !== '').join('\n');
  return markdown;
};

const getMessageMarkdown = (message: ThreadMessage | AgentErrorStreamPayload): string => {
  if ('error_id' in message) {
    let errorMessage = `**Error**: ${EMOJI_MAP.status.error} An error occurred \n`;
    errorMessage += `${message.message} \n`;
    return errorMessage;
  }

  return threadMessageMakrdown(message);
};

export const getThreadMakrdown = (threadId: string, messages: ThreadMessage[]): string => {
  const markdownBody = messages
    .map((message) => getMessageMarkdown(message))
    .filter((content) => content.trim() !== '')
    .join('\n');

  return `# Conversation\n\n_ID: ${threadId}_\n${markdownBody}`;
};
