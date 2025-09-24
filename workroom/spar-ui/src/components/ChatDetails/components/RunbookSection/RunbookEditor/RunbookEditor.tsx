import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { LexicalErrorBoundary } from '@lexical/react/LexicalErrorBoundary';
import { RichTextPlugin } from '@lexical/react/LexicalRichTextPlugin';
import { CLEAR_EDITOR_COMMAND } from 'lexical';
import { useCallback, useEffect, useState } from 'react';
import { useSnackbar } from '@sema4ai/components';
import { MARKDOWN_TRANSFORMERS } from './FunctionalToolbar/MarkdownTransformers';
// import './index.css';
import { $convertFromMarkdownString } from './plugins/lexical-markdown';
import {
  RunbookEditorContainer,
  RunbookEditorInner,
  RunbookEditorInput,
  RunbookEditorPlaceholder,
} from './styledComponents';

const EDITOR_PLACEHOLDER = 'There is no content in this runbook !';

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
      <RunbookEditorInner
        onPaste={(e) => {
          e.preventDefault();
        }}
      >
        <RichTextPlugin
          contentEditable={
            <RunbookEditorInput
              loadingEditorContents={loadingEditorContents}
              onPaste={(e) => {
                e.preventDefault();
              }}
              aria-placeholder={EDITOR_PLACEHOLDER}
              placeholder={<RunbookEditorPlaceholder>{EDITOR_PLACEHOLDER}</RunbookEditorPlaceholder>}
              disabled={loadingEditorContents}
            />
          }
          ErrorBoundary={LexicalErrorBoundary}
        />
      </RunbookEditorInner>
    </RunbookEditorContainer>
  );
};

export default RunbookEditor;
