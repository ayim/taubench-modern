import { styled } from '@sema4ai/theme';

export const Main = styled.main`
  background: ${({ theme }) => theme.colors.background.primary.color};
  height: 100%;
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-rows: auto 1fr;
  grid-template-areas: 'header header' 'aside section';

  // ${({ theme }) => theme.screen.m} {
  //   grid-template-columns: 1fr;
  //   grid-template-rows: 72px auto 1fr;
  //   grid-template-areas: 'header' 'aside' 'section';
  // }

  > header {
    grid-area: header;
  }

  > aside {
    overflow: auto;
    grid-area: aside;
  }

  > section {
    overflow: auto;
    grid-area: section;
    display: flex;
    flex-direction: column;
    flex: 1;
  }
`;
