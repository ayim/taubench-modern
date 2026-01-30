import { FC, useMemo } from 'react';
import { Chat } from '@sema4ai/components';

interface Props {
  complete: boolean;
  platform: string | undefined;
  children: string;
}

/**
 * Extract the last title between ** markers
 * - will check for it to be at least two words
 * - avoiding regex to reduce parsing overhead
 *
 * This expect that the formatting is constant - so lets update this when there is something new in formatting
 */
const extractThoughtOpenAI = (text: string): string | null => {
  let searchEnd = text.length;

  while (searchEnd > 0) {
    const end = text.lastIndexOf('**\n', searchEnd - 1);
    if (end === -1) return null;

    const start = text.lastIndexOf('**', end - 1);
    if (start === -1) return null;

    const extracted = text.substring(start + 2, end);

    if (extracted.includes(' ')) {
      return extracted;
    }

    searchEnd = start;
  }

  return null;
};

export const formatThoughtTitle = ({
  text,
  platform,
  complete,
}: {
  text: string;
  platform: string | undefined;
  complete: boolean;
}): string => {
  const result = complete ? 'Thought' : 'Thinking';

  const parsedPlatform = platform?.toLowerCase();
  // Azure OpenAI uses the same format as OpenAI
  if (parsedPlatform === 'openai' || parsedPlatform === 'azure') {
    return extractThoughtOpenAI(text) ?? result;
  }
  return result;
};

const END_OF_LINE_REGEX = /\n+$/;
const formatContent = (content: string) => {
  return content.replace(END_OF_LINE_REGEX, '');
};

export const Thinking: FC<Props> = ({ complete, children, platform }) => {
  const thought = useMemo(
    () => formatThoughtTitle({ text: children, platform, complete }),
    [children, platform, complete],
  );
  const content = useMemo(() => formatContent(children), [children]);
  return (
    <Chat.Thinking streaming={!complete} title={thought}>
      {content}
    </Chat.Thinking>
  );
};
