import { Box } from '@sema4ai/components';
import { css, styled } from '@sema4ai/theme';

/**
 * Styles for the Lexical editor.
 * Copied directly from https://github.com/Sema4AI/sema4ai-studio/blob/develop/src/components/pages/Agents/RunbookEditor/index.scss
 */
const LexicalThemeStyles = css`
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
    border-radius: 2px;
    width: 100%;
    min-width: 100%;
    height: 100%;
    min-height: 100%;
    color: rgb(var(--color-content-primary));
    position: relative;
    line-height: 20px;
    text-align: left;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
  }

  .editor-inner {
    background: rgb(var(--color-background-panels));
    position: relative;
    width: 100%;
    min-width: 100%;
    height: 100%;
    min-height: 100%;
  }

  .editor-inner > div {
    position: relative;
    width: 100%;
    min-width: 100%;
    height: 100%;
    min-height: 100%;
  }

  .editor-input {
    position: relative;
    width: 100%;
    min-width: 100%;
    height: 100%;
    min-height: 100%;
    resize: none;
    font-size: 16px;
    line-height: 22px;

    overflow-y: scroll;

    caret-color: rgb(var(--color-content-primary));
    tab-size: 1;
    outline: 0;
    padding: 48px 64px 64px 64px;
    border: none !important;

    background-color: rgb(var(--color-background-panels));
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
    font-weight: bold;
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

  .editor-list-ul {
    padding: 0;
    margin: 0;
    margin-left: 16px;
    list-style-type: disc !important;
  }

  .editor-listitem {
    margin: 8px 32px 8px 32px;
  }

  .editor-nested-listitem {
    list-style-type: none;
  }

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
`;

export const RunbookEditorContainer = styled(Box)`
  border-radius: 2px;
  width: 100%;
  min-width: 100%;
  height: 100%;
  min-height: 100%;
  color: ${({ theme }) => theme.colors.content.primary.color};
  position: relative;
  line-height: 20px;
  text-align: left;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;

  ${LexicalThemeStyles}

    ${({ theme }) => theme.screen.s} {
    .editor-input {
      padding: 0;
    }
  }
`;

export const StyledRunbookEditorWrapper = styled(Box)`
  background-color: ${({ theme }) => theme.colors.background.primary.color};
  position: relative;
`;
