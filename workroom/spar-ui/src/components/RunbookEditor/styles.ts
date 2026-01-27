import { styled } from '@sema4ai/theme';

export const Container = styled.div`
  display: block;
  min-height: 100%;
  overflow: hidden;
  border: 1px solid ${({ theme }) => theme.colors.border.subtle.color};
  border-radius: 0 ${({ theme }) => theme.radii.$8} ${({ theme }) => theme.radii.$8} 0;
  overflow: hidden;

  hr {
    height: 2px;
    background-color: rgb(var(--color-background-subtle));
  }

  .other h2 {
    font-size: 18px;
    color: rgb(var(--color-content-subtle));
    margin-bottom: 7px;
  }

  .other a {
    color: rgb(var(--color-content-subtle));
    text-decoration: underline;
    font-size: 14px;
  }

  .other ul {
    padding: 0;
    margin: 0;
  }

  h1 {
    font-size: 24px;
    color: rgb(var(--color-content-primary));
  }

  .ltr {
    text-align: left;
  }

  .rtl {
    text-align: right;
  }

  .editor-container {
    width: 100%;
    max-width: 100%;
    height: 100%;
    min-height: 100%;
    color: rgb(var(--color-content-primary));
    position: relative;
    line-height: 20px;
    text-align: left;
  }

  .editor-inner {
    background: rgb(var(--color-background-panels));
    position: relative;
    width: 100%;
    max-width: 100%;
    height: 100%;
    min-height: 100%;
    overflow: hidden;
  }

  .editor-inner > div {
    position: relative;
    width: 100%;
    max-width: 100%;
    height: 100%;
    min-height: 100%;
  }

  .editor-input {
    position: relative;
    width: 100%;
    max-width: 100%;
    height: 100%;
    min-height: 100%;
    resize: none;
    font-size: 16px;
    line-height: 22px;
    box-sizing: border-box;

    overflow-y: scroll;
    overflow-x: hidden;

    caret-color: rgb(var(--color-content-primary));
    tab-size: 1;
    outline: 0;
    padding: 48px 64px 64px 64px;
    border: none !important;

    background-color: rgb(var(--color-background-panels));
  }

  .editor-input > * {
    max-width: 100%;
  }

  .editor-input:focus-visible {
    border: none !important;
    box-shadow: none !important;
  }

  .editor-input-disabled {
    background-color: rgb(var(--color-background-subtle)) !important;
    pointer-events: none !important;
  }

  .editor-placeholder {
    color: rgb(var(--color-content-subtle));
    overflow: hidden;
    position: absolute;
    text-overflow: ellipsis;
    top: 48px;
    left: 64px;
    font-size: 14px;
    user-select: none;
    display: inline-block;
    pointer-events: none;
    width: 100%;
    min-width: 100%;
    height: 100%;
    min-height: 100%;
  }

  .editor-text-bold {
    font-weight: bold;
  }

  .editor-text-italic {
    font-style: italic;
  }

  .editor-text-underline {
    text-decoration: underline;
  }

  .editor-text-strikethrough {
    text-decoration: line-through;
  }

  .editor-text-underlineStrikethrough {
    text-decoration: underline line-through;
  }

  .editor-text-code {
    background-color: rgb(var(--color-background-subtle));
    padding: 1px 0.25rem;
    font-family: 'DM Mono', Menlo, Consolas, Monaco, monospace;
    font-size: 94%;
  }

  .editor-link {
    color: rgb(var(--color-content-link));
    text-decoration: none;
  }

  .tree-view-output {
    display: block;
    width: 100%;
    height: 100%;
    background: rgb(var(--color-background-subtle));
    color: rgb(var(--color-content-primary));
    padding: 5px;
    font-size: 12px;
    white-space: pre-wrap;
    margin: 1px auto 10px auto;
    position: relative;
    border-bottom-left-radius: 10px;
    border-bottom-right-radius: 10px;
    overflow: auto;
    line-height: 14px;
  }

  .editor-code {
    background-color: rgb(var(--color-background-subtle));
    font-family: 'DM Mono', Menlo, Consolas, Monaco, monospace;
    display: block;
    padding: 8px 8px 8px 32px;
    line-height: 1.53;
    font-size: 13px;
    margin: 0;
    margin-top: 8px;
    margin-bottom: 8px;
    tab-size: 2;
    /* white-space: pre; */
    overflow-x: auto;
    position: relative;
    width: 100%;
  }

  .editor-tokenComment {
    color: slategray;
  }

  .editor-tokenPunctuation {
    color: #999;
  }

  .editor-tokenProperty {
    color: #905;
  }

  .editor-tokenSelector {
    color: #690;
  }

  .editor-tokenOperator {
    color: #9a6e3a;
  }

  .editor-tokenAttr {
    color: #07a;
  }

  .editor-tokenVariable {
    color: #e90;
  }

  .editor-tokenFunction {
    color: #dd4a68;
  }

  .editor-paragraph {
    margin: 0;
    margin-bottom: 12px;
    position: relative;
  }

  .editor-paragraph:last-child {
    margin-bottom: 0;
  }

  .editor-heading-h1 {
    font-size: 24px;
    color: rgb(var(--color-content-primary));
    font-weight: bold;
    margin: 0;
    margin-top: 16px;
    margin-bottom: 12px;
    padding: 0;
  }

  .editor-heading-h2 {
    font-size: 20px;
    color: rgb(var(--color-content-primary));
    font-weight: bold;
    margin: 0;
    margin-top: 16px;
    margin-bottom: 12px;
    padding: 0;
  }

  .editor-heading-h3 {
    font-size: 16px;
    color: rgb(var(--color-content-primary));
    font-weight: bolder;
    margin: 0;
    margin-top: 16px;
    margin-bottom: 12px;
    padding: 0;
  }

  .editor-heading-h4 {
    font-size: 14px;
    color: rgb(var(--color-content-primary));
    text-transform: uppercase;
    font-weight: bolder;
    margin: 0;
    margin-top: 16px;
    margin-bottom: 12px;
    padding: 0;
  }

  .editor-heading-h5 {
    font-size: 12px;
    color: rgb(var(--color-content-primary));
    text-transform: uppercase;
    font-weight: bolder;
    margin: 0;
    margin-top: 16px;
    margin-bottom: 12px;
    padding: 0;
  }

  .editor-quote {
    margin: 0;
    margin-left: 20px;
    font-size: 15px;
    color: rgb(var(--color-content-subtle));
    border-left-color: rgb(var(--color-border-subtle));
    border-left-width: 4px;
    border-left-style: solid;
    padding-left: 16px;
  }

  .editor-list-ol {
    padding: 0;
    margin: 0;
    margin-left: 16px;
    list-style-type: decimal !important;
  }

  // Nested ordered lists with different numbering formats
  .editor-list-ol .editor-list-ol {
    list-style-type: lower-alpha !important;
  }

  .editor-list-ol .editor-list-ol .editor-list-ol {
    list-style-type: lower-roman !important;
  }

  .editor-list-ol .editor-list-ol .editor-list-ol .editor-list-ol {
    list-style-type: decimal !important;
  }

  .editor-list-ul {
    padding: 0;
    margin: 0;
    margin-left: 16px;
    list-style-type: disc !important;
  }

  // Nested unordered lists with different bullet styles
  .editor-list-ul .editor-list-ul {
    list-style-type: circle !important;
  }

  .editor-list-ul .editor-list-ul .editor-list-ul {
    list-style-type: square !important;
  }

  .editor-list-ul .editor-list-ul .editor-list-ul .editor-list-ul {
    list-style-type: disc !important;
  }

  .editor-listitem {
    margin: 8px 0px 8px 32px;
  }

  // This class is applied to list items that contain nested lists
  // We use 'none' to prevent double numbering on the parent item
  // .editor-nested-listitem {
  //   list-style-type: none;
  // }

  pre::-webkit-scrollbar {
    background: transparent;
    width: 10px;
  }

  pre::-webkit-scrollbar-thumb {
    background: rgb(var(--color-background-subtle));
  }

  .debug-timetravel-panel {
    overflow: hidden;
    padding: 0 0 10px 0;
    margin: auto;
    display: flex;
  }

  .debug-timetravel-panel-slider {
    padding: 0;
    flex: 8;
  }

  .debug-timetravel-panel-button {
    padding: 0;
    border: 0;
    background: none;
    flex: 1;
    color: rgb(var(--color-content-primary));
    font-size: 12px;
  }

  .debug-timetravel-panel-button:hover {
    text-decoration: underline;
  }

  .debug-timetravel-button {
    border: 0;
    padding: 0;
    font-size: 12px;
    top: 10px;
    right: 15px;
    position: absolute;
    background: none;
    color: rgb(var(--color-content-primary));
  }

  .debug-timetravel-button:hover {
    text-decoration: underline;
  }

  /* For Webkit-based browsers (Chrome, Safari and Opera) */
  .scrollbar-hide::-webkit-scrollbar {
    display: none;
  }

  /* For IE, Edge and Firefox */
  .scrollbar-hide {
    -ms-overflow-style: none;
    /* IE and Edge */
    scrollbar-width: none;
    /* Firefox */
  }

  /* Table Styles */
  .editor-table {
    border-collapse: collapse;
    border-spacing: 0;
    table-layout: fixed;
    width: 100%;
    max-width: 100%;
    margin: 16px 0;
    border: 1px solid rgb(var(--color-border-primary));
    display: table;
  }

  .editor-table-cell {
    border: 1px solid rgb(var(--color-border-primary));
    width: auto;
    min-width: 75px;
    vertical-align: top;
    text-align: center;
    padding: 8px 12px;
    position: relative;
    outline: none;
    background-color: rgb(var(--color-background-panels));
    word-wrap: break-word;
    overflow-wrap: break-word;
    white-space: normal;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .editor-table-cell-header {
    background-color: rgb(var(--color-background-subtle-light));
    font-weight: 600;
    text-align: center;
  }

  /* Table Action Button */
  .table-action-button {
    display: flex;
    align-items: center;
    justify-content: center;
    transition: opacity 0.2s ease-in-out;
  }

  // Suggestion Node Renderer
  .suggestion-node {
    width: 100%;

    // For H1 use .editor-heading-h1
    h1 {
      @extend .editor-heading-h1;
    }
    h2 {
      @extend .editor-heading-h2;
    }
    h3 {
      @extend .editor-heading-h3;
    }
    ol {
      @extend .editor-list-ol;
    }
    ul {
      @extend .editor-list-ul;

      ul {
        @extend .editor-list-ul;
      }

      li {
        @extend .editor-listitem;
      }
    }
    p {
      @extend .editor-paragraph;
    }
    blockquote {
      @extend .editor-quote;
    }
    table {
      @extend .editor-table;
    }
    td {
      @extend .editor-table-cell;
    }
    th {
      @extend .editor-table-cell-header;
    }
    code {
      @extend .editor-text-code;
      word-break: break-all;
    }
    pre {
      @extend .editor-code;
    }
    ul {
      list-style-type: disc !important;
      li {
        list-style-type: disc !important;
      }
    }
    ol {
      list-style-type: decimal !important;
      li {
        list-style-type: decimal !important;
      }
    }
  }

  // Allow suggestion node buttons to overflow table cells and code blocks
  .editor-table-cell:has([data-lexical-suggestion]),
  .editor-table-cell-header:has([data-lexical-suggestion]) {
    overflow: visible !important;
  }

  // Allow overflow for table rows containing suggestions
  .editor-table:has([data-lexical-suggestion]) {
    overflow: visible !important;
  }

  // Also ensure the code block allows overflow when it has suggestions
  .editor-code:has([data-lexical-suggestion]) {
    overflow: visible !important;
  }
`;
