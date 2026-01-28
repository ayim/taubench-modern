import { Button } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';

export const StyledDeleteButton = styled(Button)`
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  min-width: 32px !important;
  width: 32px !important;
  height: 32px !important;

  div {
    width: 32px !important;
  }
`;

export const StyledRestoreButton = styled(Button)`
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  min-width: 32px !important;
  width: 32px !important;
  height: 32px !important;

  div {
    width: 32px !important;
  }
  background-color: ${({ theme }) => theme.colors.content.success.color} !important;
  border-color: ${({ theme }) => theme.colors.content.success.color} !important;
  color: ${({ theme }) => theme.colors.content.primary.color} !important;
  opacity: 1 !important;

  &:hover:not(:disabled) {
    background-color: ${({ theme }) => theme.colors.content.success.hovered.color} !important;
    border-color: ${({ theme }) => theme.colors.content.success.hovered.color} !important;
  }
`;
