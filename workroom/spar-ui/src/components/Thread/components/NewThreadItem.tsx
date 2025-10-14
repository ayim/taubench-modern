import { IconPlus } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { FC } from 'react';
import { useCreateThread } from '../../../hooks/useCreateThread';

const Container = styled.button`
  padding: 0 ${({ theme }) => theme.space.$8};
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space.$6};
  height: ${({ theme }) => theme.sizes.$36};
  width: 100%;
  background: none;
  color: ${({ theme }) => theme.colors.content.subtle.light.color};

  &:hover {
    color: ${({ theme }) => theme.colors.content.primary.color};
  }

  &:disabled {
    pointer-events: none;
    color: ${({ theme }) => theme.colors.content.subtle.light.color};
  }
`;

export const NewThreadItem: FC = () => {
  const { onNewThread, isCreatingThread } = useCreateThread();

  return (
    <Container disabled={isCreatingThread} onClick={onNewThread}>
      <IconPlus />
      New Chat
    </Container>
  );
};
