/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck

import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { ContentEditable } from '@lexical/react/LexicalContentEditable';
import { LexicalErrorBoundary } from '@lexical/react/LexicalErrorBoundary';
import { RichTextPlugin } from '@lexical/react/LexicalRichTextPlugin';
import { Box, useSnackbar } from '@sema4ai/components';
import { CLEAR_EDITOR_COMMAND } from 'lexical';
import { useCallback, useEffect, useState } from 'react';
import { MARKDOWN_TRANSFORMERS } from './FunctionalToolbar/MarkdownTransformers';
import { $convertFromMarkdownString } from './plugins/lexical-markdown';
import { RunbookEditorContainer } from './styledComponents';

type RunbookEditorProps = {
  runbookMarkdown: string;
};

const RunbookEditor = ({ runbookMarkdown }: RunbookEditorProps) => {
  const [editor] = useLexicalComposerContext();
  const [loadingEditorContents, setLoadingEditorContents] = useState<boolean>(true);
  const { addSnackbar } = useSnackbar();

  const onBoot = useCallback(async () => {
    setLoadingEditorContents(true);
    try {
      editor.dispatchCommand(CLEAR_EDITOR_COMMAND, undefined);
      editor.focus();

      editor.update(
        () => {
          $convertFromMarkdownString(runbookMarkdown, undefined, MARKDOWN_TRANSFORMERS, false);
        },
        { discrete: true },
      );
    } catch {
      addSnackbar({ message: 'Failed to load contents', variant: 'danger' });
    } finally {
      setLoadingEditorContents(false);
    }
  }, [runbookMarkdown, editor]);

  useEffect(() => {
    onBoot();
  }, [onBoot]);

  return (
    <RunbookEditorContainer>
      <Box
        className="editor-inner"
        onPaste={(e) => {
          e.preventDefault();
        }}
      >
        <RichTextPlugin
          contentEditable={
            <ContentEditable
              className={`editor-input ${loadingEditorContents ? 'editor-input-disabled' : ''}`}
              onPaste={(e) => {
                e.preventDefault();
              }}
              disabled={loadingEditorContents}
            />
          }
          ErrorBoundary={LexicalErrorBoundary}
        />
      </Box>
    </RunbookEditorContainer>
  );
};

export default RunbookEditor;
