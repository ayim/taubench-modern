import { FC } from 'react';
import { Box, Button, Dialog, Typography } from '@sema4ai/components';
import { LexicalComposer } from '@lexical/react/LexicalComposer';
import { HorizontalRuleNode } from '@lexical/react/LexicalHorizontalRuleNode';
import { HeadingNode, QuoteNode } from '@lexical/rich-text';
import { TableCellNode, TableNode, TableRowNode } from '@lexical/table';
import { ListItemNode, ListNode } from '@lexical/list';
import { AutoLinkNode, LinkNode } from '@lexical/link';
import { CodeNode } from '@lexical/code';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { $getRoot } from 'lexical';

import { RunbookEditor } from './RunbookEditor';
import { ToolbarPlugin } from './plugins/ToolbarPlugin';
import { TableOfContentsPlugin } from './plugins/TableOfContentsPlugin';

import { StatusBar } from './StatusBar/StatusBar';
import { ArtificialRootNode } from './plugins/nodes/LexicalArtificialRootNode';
import { HighlightNode } from './plugins/HighlightNode';
import { $convertToMarkdownString } from './plugins/lexical-markdown';
import { MARKDOWN_TRANSFORMERS } from './plugins/lexical-markdown/MarkdownTransformers';

type Props = {
  onClose: (value?: string) => void;
  value: string;
};

const theme = {
  code: 'editor-code',
  heading: {
    h1: 'editor-heading-h1',
    h2: 'editor-heading-h2',
    h3: 'editor-heading-h3',
    h4: 'editor-heading-h4',
    h5: 'editor-heading-h5',
  },
  image: 'editor-image',
  link: 'editor-link',
  list: {
    listitem: 'editor-listitem',
    nested: {
      listitem: 'editor-listitem',
    },
    ol: 'editor-list-ol',
    ul: 'editor-list-ul',
  },
  ltr: 'ltr',
  paragraph: 'editor-paragraph',
  placeholder: 'editor-placeholder',
  quote: 'editor-quote',
  rtl: 'rtl',
  text: {
    bold: 'editor-text-bold',
    code: 'editor-text-code',
    hashtag: 'editor-text-hashtag',
    italic: 'editor-text-italic',
    overflowed: 'editor-text-overflowed',
    strikethrough: 'editor-text-strikethrough',
    underline: 'editor-text-underline',
    underlineStrikethrough: 'editor-text-underlineStrikethrough',
  },
  table: 'editor-table',
  tableCell: 'editor-table-cell',
  tableCellHeader: 'editor-table-cell-header',
  tableRow: 'editor-table-row',
};

const editorConfig = {
  namespace: 'Runbook Editor',
  nodes: [
    HeadingNode,
    QuoteNode,
    ListNode,
    ListItemNode,
    LinkNode,
    AutoLinkNode,
    CodeNode,
    HorizontalRuleNode,
    ArtificialRootNode,
    HighlightNode,
    TableNode,
    TableCellNode,
    TableRowNode,
  ],
  // Handling of errors during update
  onError(error: Error) {
    throw error;
  },
  // The editor theme
  theme,
};

const DialogContent: FC<Props> = ({ onClose, value }) => {
  const [editor] = useLexicalComposerContext();

  const onSaveChanges = () => {
    editor.getEditorState().read(async () => {
      const root = $getRoot();
      const markdown = $convertToMarkdownString(MARKDOWN_TRANSFORMERS, root, true);
      onClose(markdown);
    });
  };

  return (
    <Dialog open onClose={onSaveChanges} size="page">
      <Dialog.Bar onBackClick={onSaveChanges}>
        <Typography variant="display-small">Runbook Editor</Typography>
      </Dialog.Bar>
      <Dialog.Content>
        <Box display="flex" height="100%" maxHeight="100%" width="100%" flexDirection="column" overflow="hidden">
          <Box display="flex" height="44px" width="100%" flexDirection="row" justifyContent="space-between">
            <ToolbarPlugin />
          </Box>
          <Box
            display="flex"
            height="100%"
            maxHeight="100%"
            minHeight="calc(100% - 130px)"
            width="100%"
            flexDirection="row"
          >
            <TableOfContentsPlugin />

            {/* EDITOR TEXTAREA */}
            <Box display="flex" flexDirection="column" height="100%" width="100%">
              <RunbookEditor value={value} />
            </Box>
          </Box>
          {/* STATUS BAR */}
          <Box display="flex" height="32px" width="100%" flexDirection="row">
            <StatusBar />
          </Box>
        </Box>
      </Dialog.Content>
      <Dialog.Actions>
        <Dialog.Actions>
          <Button variant="primary" onClick={onSaveChanges} round>
            Save
          </Button>
          <Button variant="secondary" onClick={() => onClose()} round>
            Cancel
          </Button>
        </Dialog.Actions>
      </Dialog.Actions>
    </Dialog>
  );
};

export const RunbookDialog: FC<Props> = ({ onClose, value }) => {
  return (
    <LexicalComposer initialConfig={editorConfig}>
      <DialogContent onClose={onClose} value={value} />
    </LexicalComposer>
  );
};
