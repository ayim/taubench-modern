import { FC, useEffect, useState } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { $getRoot } from 'lexical';

type RunbookStatistics = {
  nrOfChars: number;
  nrOfWords: number;
  nrOfSentences: number;
};

const Divider: FC = () => {
  return <Box backgroundColor="background.subtle.light" width={2} height="80%" mx={4} />;
};

const sentenceCount = (text: string) => {
  const t = text.replace(/\s+/g, ' ').trim();
  if (!t) return 0;

  const matches = t.match(/[^.!?]+(?:[.!?]+|$)/g);
  if (!matches) return 0;

  return matches
    .map((s) => s.trim())
    .filter(Boolean)
    .filter((s) => /[A-Za-z0-9\u00C0-\u024F\u0400-\u04FF]/.test(s)).length;
};

const wordCount = (text: string) => {
  const t = text.replace(/\s+/g, ' ').trim();
  if (!t) return 0;
  const matches = t.match(/[\p{L}\p{N}]+/gu);
  return matches ? matches.length : 0;
};

const calculateStatistics = (textContent: string): RunbookStatistics => ({
  nrOfChars: textContent.length,
  nrOfWords: wordCount(textContent),
  nrOfSentences: sentenceCount(textContent),
});

export const StatusBar: FC = () => {
  const [editor] = useLexicalComposerContext();

  const [statistics, setStatistics] = useState<RunbookStatistics>();

  useEffect(() => {
    editor.getEditorState().read(() => {
      const textContent = $getRoot().getTextContent();
      setStatistics(calculateStatistics(textContent));
    });

    return editor.registerTextContentListener((textContent) => {
      setStatistics(calculateStatistics(textContent));
    });
  }, [editor]);

  return (
    <Box display="flex" alignItems="center" gap="$8" justifyContent="flex-end" flex="1">
      <Typography
        variant="body-small"
        color="content.subtle.light"
      >{`${statistics?.nrOfChars || 0} characters`}</Typography>
      <Divider />
      <Typography variant="body-small" color="content.subtle.light">{`${statistics?.nrOfWords || 0} words`}</Typography>
      <Divider />
      <Typography
        variant="body-small"
        color="content.subtle.light"
      >{`${statistics?.nrOfSentences} sentences`}</Typography>
    </Box>
  );
};
