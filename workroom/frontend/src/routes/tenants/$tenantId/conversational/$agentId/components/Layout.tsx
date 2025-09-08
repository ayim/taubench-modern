import { styled } from '@sema4ai/theme';

export const Layout = styled.section`
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-rows: auto 1fr;
  grid-template-areas: 'header header' 'aside section';

  > header {
    grid-area: header;
  }

  > aside {
    grid-area: aside;
  }

  > section {
    grid-area: section;
  }
`;
