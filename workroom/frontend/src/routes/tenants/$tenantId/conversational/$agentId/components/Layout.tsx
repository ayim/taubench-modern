import { styled } from '@sema4ai/theme';

export const Layout = styled.section`
  display: grid;
  grid-template-columns: minmax(0, auto) 1fr minmax(0, auto);
  grid-template-rows: auto 1fr;
  grid-template-areas: 'threads header header' 'threads section sidebar';

  > header {
    grid-area: header;
  }

  &:has(> div) > header {
    border-bottom: 1px solid ${({ theme }) => theme.colors.border.subtle.color};
  }

  > aside {
    grid-area: threads;
    overflow-x: hidden;
    max-width: 100%;

    > div {
      overflow-x: hidden;
    }
  }

  > section {
    grid-area: section;
    min-width: 360px;
  }

  > div {
    grid-area: sidebar;
    max-width: 100%;
  }

  max-height: 100vh;
`;
