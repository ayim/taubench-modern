import { css, styled } from '@sema4ai/theme';

export const Layout = styled.section<{ workItemListOnly?: boolean }>`
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-rows: auto 1fr;
  grid-template-areas: 'header header' 'aside section';

  overflow: hidden;
  max-height: 100vh;

  > header {
    grid-area: header;
  }

  > aside {
    grid-area: aside;
    overflow: hidden;
  }

  > section {
    grid-area: section;
  }

  ${({ workItemListOnly }) =>
    workItemListOnly &&
    css`
      grid-template-areas: 'header header' 'aside aside';
      > aside {
        width: 100%;
      }
    `}
`;
