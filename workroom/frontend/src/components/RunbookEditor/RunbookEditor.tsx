import { FC, useCallback, useEffect, useState } from 'react';

import { AutoFocusPlugin } from '@lexical/react/LexicalAutoFocusPlugin';
import { ContentEditable } from '@lexical/react/LexicalContentEditable';
import { LexicalErrorBoundary } from '@lexical/react/LexicalErrorBoundary';
import { HistoryPlugin } from '@lexical/react/LexicalHistoryPlugin';
import { RichTextPlugin } from '@lexical/react/LexicalRichTextPlugin';
import { ListPlugin } from '@lexical/react/LexicalListPlugin';
import { AutoLinkPlugin, createLinkMatcherWithRegExp } from '@lexical/react/LexicalAutoLinkPlugin';
import { LinkPlugin } from '@lexical/react/LexicalLinkPlugin';
import { ClickableLinkPlugin } from '@lexical/react/LexicalClickableLinkPlugin';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { HorizontalRulePlugin } from '@lexical/react/LexicalHorizontalRulePlugin';
import { TablePlugin } from '@lexical/react/LexicalTablePlugin';

import { CLEAR_EDITOR_COMMAND, INDENT_CONTENT_COMMAND, OUTDENT_CONTENT_COMMAND } from 'lexical';

import { EMAIL_REGEX, URL_REGEX } from './utils';

import { MARKDOWN_TRANSFORMERS } from './plugins/lexical-markdown/MarkdownTransformers';
import FloatingLinkEditorPlugin from './plugins/FloatingLinkEditorPlugin';
import TableActionPlugin from './plugins/TableActionPlugin';
import { $convertFromMarkdownString } from './plugins/lexical-markdown';
import { SuggestionActionsPlugin } from './plugins/SuggestionActionsPlugin';
import { MarkdownClipboardPlugin } from './plugins/MarkdownClipboardPlugin';
import { Container } from './styles';

const MATCHERS = [
  createLinkMatcherWithRegExp(URL_REGEX, (text) => {
    return text.startsWith('http') ? text : `https://${text}`;
  }),
  createLinkMatcherWithRegExp(EMAIL_REGEX, (text) => {
    return `mailto:${text}`;
  }),
];

type Props = {
  value: string;
};

export const RunbookEditor: FC<Props> = ({ value }) => {
  const [editor] = useLexicalComposerContext();

  const [floatingAnchorElem, setFloatingAnchorElem] = useState<HTMLDivElement | undefined>(undefined);
  const [isLinkEditMode, setIsLinkEditMode] = useState<boolean>(false);

  const onRef = useCallback((_floatingAnchorElem: HTMLDivElement | null) => {
    if (_floatingAnchorElem !== null) {
      setFloatingAnchorElem(_floatingAnchorElem);
    }
  }, []);

  const captureKeysInEditor: React.KeyboardEventHandler = useCallback(
    (e) => {
      // Capture the tab key
      if (e.key === 'Tab') {
        // Disable the default tab behavior
        e.preventDefault();
        e.stopPropagation();
        e.nativeEvent.stopImmediatePropagation?.();

        // Dispatch the appropriate command based on the shift key
        editor.dispatchCommand(e.shiftKey ? OUTDENT_CONTENT_COMMAND : INDENT_CONTENT_COMMAND, undefined);
      }
    },
    [editor],
  );

  useEffect(() => {
    editor.dispatchCommand(CLEAR_EDITOR_COMMAND, undefined);
    editor.focus();

    editor.update(
      () => {
        $convertFromMarkdownString(value, MARKDOWN_TRANSFORMERS, undefined, true);
      },
      { discrete: true },
    );
  }, []);

  return (
    <Container>
      <div className="editor-container" onKeyDownCapture={captureKeysInEditor}>
        <div className="editor-inner">
          <RichTextPlugin
            contentEditable={
              <div ref={onRef}>
                <ContentEditable id="runbook-editor-input" className="editor-input" placeholder={undefined} />
              </div>
            }
            ErrorBoundary={LexicalErrorBoundary}
          />
          <HistoryPlugin />
          <AutoFocusPlugin />
          <ListPlugin />
          <HorizontalRulePlugin />
          <ClickableLinkPlugin disabled />
          <AutoLinkPlugin matchers={MATCHERS} />
          <LinkPlugin />
          <FloatingLinkEditorPlugin
            anchorElem={floatingAnchorElem}
            isLinkEditMode={isLinkEditMode}
            setIsLinkEditMode={setIsLinkEditMode}
          />
          <TablePlugin />
          <TableActionPlugin anchorElem={floatingAnchorElem} />
          <MarkdownClipboardPlugin />
        </div>
        <SuggestionActionsPlugin />
      </div>
    </Container>
  );
};
