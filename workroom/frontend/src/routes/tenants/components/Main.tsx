import { styled } from '@sema4ai/theme';

export const Main = styled.main`
  background: ${({ theme }) => theme.colors.background.primary.color};
  height: 100%;
  width: 100%;
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-areas: 'aside section';
  overflow: hidden;

  ${({ theme }) => theme.screen.m} {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
    grid-template-areas: 'aside' 'section';
  }

  > aside {
    grid-area: aside;
    overflow-x: hidden;
    > div {
      overflow-x: hidden;
    }
  }

  > section {
    grid-area: section;
  }
`;
