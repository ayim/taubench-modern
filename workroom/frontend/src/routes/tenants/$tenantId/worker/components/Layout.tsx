import { styled } from '@sema4ai/theme';

export const Layout = styled.section<{ workItemListOnly?: boolean }>`
  display: grid;
  grid-template-columns: auto 1fr auto;
  grid-template-rows: auto 1fr;
  grid-template-areas: 'workitems header header' 'workitems section sidebar';

  overflow: hidden;
  max-height: 100vh;

  > header {
    grid-area: header;
  }

  > aside {
    grid-area: workitems;
    overflow-x: hidden;
    max-width: 100%;

    > div {
      overflow-x: hidden;
    }
  }

  > section {
    grid-area: section;
  }

  > div {
    grid-area: sidebar;
  }
`;
