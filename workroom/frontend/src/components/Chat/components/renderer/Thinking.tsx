import { FC, useEffect, useMemo, useState } from 'react';
import { Chat } from '@sema4ai/components';

interface Props {
  complete: boolean;
  platform: string | undefined;
  children: string;
  durationSeconds?: number;
  startedAt?: string;
  messageComplete?: boolean;
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
  durationSeconds,
  messageComplete,
}: {
  text: string;
  platform: string | undefined;
  complete: boolean;
  durationSeconds?: number;
  messageComplete?: boolean;
}): string => {
  // Show "Thinking..." until the entire message is done, not just the individual thought
  const isFullyDone = complete && (messageComplete ?? true);
  const baseWord = isFullyDone ? 'Thought' : 'Thinking';
  const result =
    durationSeconds !== undefined
      ? `${baseWord} for ${durationSeconds} second${durationSeconds === 1 ? '' : 's'}`
      : baseWord;

  const parsedPlatform = platform?.toLowerCase();
  if (parsedPlatform === 'openai') {
    return extractThoughtOpenAI(text) ?? result;
  }
  return result;
};

const END_OF_LINE_REGEX = /\n+$/;
const formatContent = (content: string) => {
  return content.replace(END_OF_LINE_REGEX, '');
};

export const Thinking: FC<Props> = ({ complete, children, platform, durationSeconds, startedAt, messageComplete }) => {
  const [liveDuration, setLiveDuration] = useState<number | undefined>(undefined);

  // Calculate live duration while streaming
  useEffect(() => {
    if (!startedAt || complete) {
      return undefined;
    }

    const calculateDuration = () => {
      try {
        const started = new Date(startedAt).getTime();
        const now = Date.now();
        setLiveDuration(Math.round((now - started) / 1000));
      } catch {
        // Keep existing value on error
      }
    };

    calculateDuration();
    const interval = setInterval(calculateDuration, 1000);
    return () => clearInterval(interval);
  }, [complete, startedAt]);

  // Prefer server duration, fall back to client-calculated duration
  const effectiveDuration = durationSeconds ?? liveDuration;

  const thought = useMemo(
    () => formatThoughtTitle({ text: children, platform, complete, durationSeconds: effectiveDuration, messageComplete }),
    [children, platform, complete, effectiveDuration, messageComplete],
  );
  const content = useMemo(() => formatContent(children), [children]);
  return (
    <Chat.Thinking streaming={!complete || !messageComplete} title={thought}>
      {content}
    </Chat.Thinking>
  );
};
