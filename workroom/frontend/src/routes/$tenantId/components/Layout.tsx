import { styled } from '@sema4ai/theme';

export const Layout = styled.div`
  display: flex;
  justify-content: stretch;
  background: ${({ theme }) => theme.colors.background.primary.color};
  height: 100%;
  width: 100%;
  > section {
    width: 100%;
    height: 100%;
  }
`;
