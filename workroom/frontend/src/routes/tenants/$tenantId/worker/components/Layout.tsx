import { styled } from '@sema4ai/theme';

export const Layout = styled.section<{ workItemListOnly?: boolean }>`
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto 1fr;
  grid-template-areas: 'header header' 'section aside';

  overflow: hidden;
  max-height: 100vh;

  > header {
    grid-area: header;
  }

  > section {
    grid-area: section;
  }

  > aside {
    grid-area: aside;
  }
`;
