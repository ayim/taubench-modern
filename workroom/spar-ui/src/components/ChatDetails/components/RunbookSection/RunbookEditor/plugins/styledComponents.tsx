import { HeadingTagType } from '@lexical/rich-text';
import { Box } from '@sema4ai/components';
import { css, styled } from '@sema4ai/theme';

export const StyledTableOfContents = styled(Box)`
  color: #65676b;
  position: relative;
  display: flex;
  flex-direction: row;
  justify-content: flex-start;
  z-index: 1;
`;

export const StyledHeadingItem = styled(Box)<{ headingLevel: HeadingTagType }>`
  ${({ headingLevel }) => {
    const styles = {
      h1: css`
        li {
          font-weight: 600;
          font-size: 14px;
        }
      `,
      h2: css`
        font-weight: 500;
        margin-left: 8px;
      `,
      h3: css`
        margin-left: 16px;
      `,
      h4: css`
        margin-left: 16px;
      `,
      h5: css`
        margin-left: 16px;
      `,
      h6: css`
        margin-left: 16px;
      `,
    };
    return styles[headingLevel];
  }}
`;

export const StyledHeadings = styled.ul`
  list-style: none;
  margin-top: 0;
  width: 100%;
  height: 100%;
  overflow: scroll;
  overflow-x: hidden;
  overflow-y: auto;
  -ms-overflow-style: none;
  /* IE and Edge */
  scrollbar-width: none;
  /* Firefox */

  ::-webkit-scrollbar {
    display: none;
  }
`;

export const StyledNormalHeadingWrapper = styled(Box)<{ selected: boolean }>`
  margin-left: 20px;
  margin-bottom: 8px;
  position: relative;

  :hover {
    text-decoration: underline;
  }

  ${({ selected }) =>
    selected &&
    css`
      ::before {
        content: ' ';
        position: absolute;
        display: inline-block;
        left: -12px;
        top: 0px;
        z-index: 10;
        height: 100%;
        width: 1px;
        background-color: #2e5842;
        border: solid 1px #2e5842;
      }
    `}
`;

export const StyledNormalHeading = styled.li<{ selected: boolean }>`
  cursor: pointer;
  line-height: 20px;
  font-size: 12px;

  ${({ selected }) =>
    selected &&
    css`
      color: #2e5842;
      font-weight: 600;
      position: relative;
    `}
`;
