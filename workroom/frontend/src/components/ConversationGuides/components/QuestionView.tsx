import { FC } from 'react';
import { IconArrowUp, IconCheck2, IconCopy } from '@sema4ai/icons';
import { Box, Button, Typography, useClipboard } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { useParams } from '@tanstack/react-router';

import { useMessageStream } from '~/hooks';
import { useAgentOAuthStateQuery } from '~/queries/agents';

type Props = {
  question: string;
};

const Container = styled(Box)<{ disabled: boolean }>`
  ${({ disabled }) =>
    disabled &&
    `
    opacity: 0.6;
    cursor: not-allowed;
    pointer-events: none;
  `}
`;

export const QuestionView: FC<Props> = ({ question }) => {
  const { copyToClipboard, copiedToClipboard } = useClipboard();
  const { agentId, threadId } = useParams({
    from: '/tenants/$tenantId/conversational/$agentId/$threadId/conversation-guides/',
  });

  const { sendMessage, isStreaming, uploadingFiles } = useMessageStream({ agentId, threadId });
  const { data: oAuthState = [] } = useAgentOAuthStateQuery({ agentId });
  const requiresOAuth = oAuthState.some((state) => !state.isAuthorized);

  const canSendMessage = !requiresOAuth && !isStreaming && !uploadingFiles;

  const onSendMessage = () => {
    sendMessage({ text: question, type: 'text' }, []);
  };

  const onCopyQuestion = () => {
    copyToClipboard(question);
  };

  return (
    <Container
      display="flex"
      flexDirection="row"
      alignItems="center"
      justifyContent="space-between"
      p="$8"
      pl="$16"
      gap="$8"
      borderRadius="$16"
      boxShadow="medium"
      backgroundColor="background.panels"
      disabled={!canSendMessage}
    >
      <Typography variant="body-large-loose" $nowrap truncate={1}>
        {question}
      </Typography>

      <Box ml="auto" display="flex" alignItems="center" gap="$4">
        <Button
          aria-label="Copy question"
          variant="ghost"
          round
          icon={copiedToClipboard ? IconCheck2 : IconCopy}
          onClick={onCopyQuestion}
        />
        <Button
          icon={IconArrowUp}
          aria-label="Send message"
          variant="primary"
          round
          type="button"
          size="small"
          onClick={onSendMessage}
          disabled={!canSendMessage}
        />
      </Box>
    </Container>
  );
};
