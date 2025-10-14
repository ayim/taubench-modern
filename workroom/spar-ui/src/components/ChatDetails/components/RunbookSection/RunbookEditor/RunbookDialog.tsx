import { CodeNode } from '@lexical/code';
import { AutoLinkNode, LinkNode } from '@lexical/link';
import { ListItemNode, ListNode } from '@lexical/list';
import { InitialConfigType, LexicalComposer } from '@lexical/react/LexicalComposer';
import { HorizontalRuleNode } from '@lexical/react/LexicalHorizontalRuleNode';
import { HeadingNode, QuoteNode } from '@lexical/rich-text';
import { Box, Dialog, Typography } from '@sema4ai/components';
import { memo } from 'react';
import { lexicalTheme } from './lexicalTheme';
import { ArtificialRootNode } from './plugins/nodes/LexicalArtificialRootNode';
import { StyledTOCWrapper } from './plugins/styledComponents';
import TableOfContentsPlugin from './plugins/TableOfContentsPlugin';
import RunbookEditor from './RunbookEditor';
import { StyledRunbookEditorWrapper } from './styledComponents';

const editorConfig: InitialConfigType = {
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
  ],
  // Handling of errors during update
  onError(error: Error) {
    throw error;
  },
  // The editor theme
  theme: lexicalTheme,
  editable: false,
};

type RunbookDialogProps = {
  agentName: string;
  runbookMarkdown: string;
  open: boolean;
  onClose: () => void;
};

export const RunbookDialog = memo<RunbookDialogProps>(({ open, onClose, agentName, runbookMarkdown }) => {
  return (
    <Dialog open={open} size="full-screen" width="90vw" onClose={onClose}>
      <Dialog.Header>
        <Dialog.Header.Title title={`Runbook Viewer (${agentName})`} />
      </Dialog.Header>
      <Dialog.Content>
        <LexicalComposer initialConfig={editorConfig}>
          <Box display="flex" height="100%" width="100%" maxHeight="100%" maxWidth="100%">
            <StyledTOCWrapper>
              <Box ml="$32" mt="$16">
                <Typography variant="body-small" fontWeight={700}>
                  Outline
                </Typography>
              </Box>

              <Box overflow="auto" ml="$12">
                <TableOfContentsPlugin />
              </Box>
            </StyledTOCWrapper>

            <StyledRunbookEditorWrapper flexBasis={0} flexGrow={4}>
              <RunbookEditor runbookMarkdown={runbookMarkdown} />
            </StyledRunbookEditorWrapper>
          </Box>
        </LexicalComposer>
      </Dialog.Content>
    </Dialog>
  );
});
