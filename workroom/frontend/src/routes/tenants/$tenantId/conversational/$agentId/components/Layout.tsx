import { styled } from '@sema4ai/theme';

export const Layout = styled.section`
  display: grid;
  grid-template-columns: auto 1fr auto;
  grid-template-rows: auto 1fr;
  grid-template-areas: 'header header header' 'threads section sidebar';

  > header {
    grid-area: header;
  }

  > aside {
    grid-area: threads;
  }

  > section {
    grid-area: section;
  }

  > div {
    grid-area: sidebar;
  }

  max-height: 100vh;
`;
