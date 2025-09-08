import { styled } from '@sema4ai/theme';

export const Header = styled.header<{ $sidebarExpanded: boolean }>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space.$16};
  height: ${({ theme }) => theme.sizes.$64};
  padding: ${({ theme }) => theme.space.$14} ${({ theme }) => theme.space.$20};
  padding-left: ${({ theme, $sidebarExpanded }) => (!$sidebarExpanded ? theme.space.$64 : theme.space.$20)};
  outline: 1px solid ${({ theme }) => theme.colors.border.primary.color};

  ${({ theme }) => theme.screen.m} {
    height: 52px;
    padding-left: 52px;
  }
`;
