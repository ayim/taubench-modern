import { Button } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';

export const StyledDeleteButton = styled(Button)`
  div {
    width: 32px !important;
  }
`;

export const StyledRestoreButton = styled(Button)`
  div {
    width: 32px !important;
  }
  background-color: ${({ theme }) => theme.colors.content.success.color} !important;
  border-color: ${({ theme }) => theme.colors.content.success.color} !important;
  color: ${({ theme }) => theme.colors.content.primary.color} !important;

  &:hover:not(:disabled) {
    background-color: ${({ theme }) => theme.colors.content.success.hovered.color} !important;
    border-color: ${({ theme }) => theme.colors.content.success.hovered.color} !important;
  }
`;
