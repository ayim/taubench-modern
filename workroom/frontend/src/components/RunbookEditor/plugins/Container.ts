import { styled } from '@sema4ai/theme';

export const Container = styled.div`
  color: rgb(var(--color-content-subtle));
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
  justify-content: flex-start;
  z-index: 1;
  overflow-y: scroll;

  .heading1 li {
    font-weight: 600;
    font-size: 14px;
  }

  .heading2 {
    font-weight: 500;
    margin-left: 8px;
  }

  .heading3 {
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
    left: 0px;
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
    margin-bottom: 8px;
    position: relative;

    :hover {
      text-decoration: underline;
    }
  }

  .toolbar {
    display: flex;
  }

  .toolbar .divider {
    width: 1px;
    height: 80%;
    background-color: rgb(var(--color-border-subtle));
    margin: 0 4px;
  }

  .toolbar-buttons {
    display: flex;
  }

  .toolbar-buttons span {
    display: flex;
    justify-content: center;
    justify-items: center;
    align-items: center;
  }

  .toolbar-buttons svg {
    width: 16px;
    height: 16px;
  }

  .link-editor {
    display: flex;
    position: absolute;
    top: 0;
    left: 0;
    z-index: 10;
    max-width: 400px;
    width: 100%;
    opacity: 0;
    background-color: #fff;
    box-shadow: 0 5px 10px rgba(0, 0, 0, 0.3);
    border-radius: 0 0 8px 8px;
    transition: opacity 0.5s;
    will-change: transform;
  }

  .actions i {
    background-size: contain;
    display: inline-block;
    height: 20px;
    width: 20px;
    vertical-align: -0.25em;
  }

  .link-editor .button.active,
  .toolbar .button.active {
    background-color: rgb(223, 232, 250);
  }

  .link-editor .link-input {
    display: block;
    width: calc(100% - 100px);
    box-sizing: border-box;
    margin: 12px 12px;
    padding: 8px 12px;
    background-color: #eee;
    border-radius: 8px;
    font-size: 15px;
    color: rgb(5, 5, 5);
    border: 0;
    outline: 0;
    position: relative;
    font-family: inherit;
  }

  .link-editor .link-view {
    display: block;
    width: 100%;
    min-height: 64px;
    padding: 8px 12px;
    font-size: 15px;
    color: rgb(5, 5, 5);
    border: 0;
    outline: 0;
    position: relative;
    font-family: inherit;
  }

  .link-editor .link-view a {
    font-size: 12px;
    color: rgb(33, 111, 219);
    display: block;
    word-break: break-word;
    width: calc(100% - 33px);
  }

  .link-editor .link-input a {
    font-size: 12px;
    color: rgb(33, 111, 219);
    text-decoration: underline;
    white-space: nowrap;
    overflow: hidden;
    margin-right: 30px;
    text-overflow: ellipsis;
  }

  .link-editor .link-input a:hover {
    text-decoration: underline;
  }

  .link-editor .font-size-wrapper,
  .link-editor .font-family-wrapper {
    display: flex;
    margin: 0 4px;
  }

  .link-editor select {
    padding: 6px;
    border: none;
    background-color: rgba(0, 0, 0, 0.075);
    border-radius: 4px;
  }
`;
