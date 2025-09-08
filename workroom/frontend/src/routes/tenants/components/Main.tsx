import { styled } from '@sema4ai/theme';

export const Main = styled.main`
  background: ${({ theme }) => theme.colors.background.primary.color};
  height: 100%;
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-areas: 'aside section';

  ${({ theme }) => theme.screen.m} {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
    grid-template-areas: 'aside' 'section';
  }

  > aside {
    grid-area: aside;
  }

  > section {
    grid-area: section;
  }
`;
