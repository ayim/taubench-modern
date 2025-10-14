import { css, styled } from '@sema4ai/theme';

/**
 * Styles for the Table of Contents.
 * Copied directly from https://github.com/Sema4AI/sema4ai-studio/blob/develop/src/components/pages/Agents/RunbookEditor/plugins/index.css
 */
const TOCThemeStyles = css`
  .table-of-contents .heading1 li {
    font-weight: 600;
    font-size: 14px;
  }

  .table-of-contents .heading2 {
    font-weight: 500;
    margin-left: 8px;
  }

  .table-of-contents .heading3 {
    margin-left: 16px;
  }

  .selected-heading {
    color: rgb(var(--color-background-success));
    font-weight: 600;
    position: relative;
  }

  .selected-heading-wrapper::before {
    content: ' ';
    position: absolute;
    display: inline-block;
    left: -12px;
    top: 0px;
    z-index: 10;
    height: 100%;
    width: 1px;
    background-color: rgb(var(--color-background-success));
    border: solid 1px rgb(var(--color-background-success));
  }

  .normal-heading {
    cursor: pointer;
    line-height: 20px;
    font-size: 12px;
  }

  .table-of-contents {
    color: rgb(var(--color-content-subtle));
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    z-index: 1;
    overflow-y: scroll;
  }

  .headings {
    list-style: none;
    margin-top: 0;
    width: 100%;
    height: 100%;
    overflow: scroll;
    overflow-x: hidden;
    overflow-y: auto;
    -ms-overflow-style: none; /* IE and Edge */
    scrollbar-width: none; /* Firefox */
  }

  /* Hide scrollbar for Chrome, Safari and Opera */
  .headings::-webkit-scrollbar {
    display: none;
  }

  .normal-heading-wrapper {
    margin-left: 20px;
    margin-bottom: 8px;
    position: relative;

    :hover {
      text-decoration: underline;
    }
  }
`;

export const StyledTOCWrapper = styled.div`
  flex-basis: 0;
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space.$16};
  border-color: ${({ theme }) => theme.colors.border.subtle.color};
  border-right-width: ${({ theme }) => theme.borderWidths.$1};
  border-style: solid;

  ${({ theme }) => theme.screen.s} {
    display: none;
  }

  ${TOCThemeStyles}
`;
