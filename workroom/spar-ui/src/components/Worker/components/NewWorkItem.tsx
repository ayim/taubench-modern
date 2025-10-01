import { IconPlus } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { useLinkProps } from '../../../common/link';
import { useParams } from '../../../hooks';

const Container = styled.a`
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

export const NewWorkItem = () => {
  const { agentId } = useParams('/workItem/$agentId');
  const linkProps = useLinkProps('/workItem/$agentId/create', { agentId });

  return (
    <Container {...linkProps}>
      <IconPlus />
      New Work Item
    </Container>
  );
};
