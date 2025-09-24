import { CodeNode } from '@lexical/code';
import { AutoLinkNode, LinkNode } from '@lexical/link';
import { ListItemNode, ListNode } from '@lexical/list';
import { InitialConfigType, LexicalComposer } from '@lexical/react/LexicalComposer';
import { HorizontalRuleNode } from '@lexical/react/LexicalHorizontalRuleNode';
import { HeadingNode, QuoteNode } from '@lexical/rich-text';
import { Box, Dialog, Typography } from '@sema4ai/components';
import { IconSema4Filled } from '@sema4ai/icons/logos';
import { memo } from 'react';
import { lexicalTheme } from './lexicalTheme';
import { ArtificialRootNode } from './plugins/nodes/LexicalArtificialRootNode';
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
    <Dialog open={open} size="medium" width="90vw" onClose={onClose}>
      <Box height="90vh" overflow="hidden" width="100%" display="grid" gridTemplateRows="auto auto 1fr" pb="$16">
        <Box display="flex" alignItems="center" gap={12} px="$24" py="$16">
          <IconSema4Filled />
          <Typography variant="display-small">Runbook Viewer</Typography>
        </Box>

        <Box
          backgroundColor="background.subtle.light.hovered"
          px="$24"
          py="$8"
          borderColor="border.subtle"
          borderBottomWidth={1}
        >
          <Typography variant="display-headline">{agentName}</Typography>
        </Box>

        <LexicalComposer initialConfig={editorConfig}>
          <Box backgroundColor="background.subtle.light" display="flex" overflow="hidden">
            <Box
              flexBasis={0}
              flexGrow={1}
              display="flex"
              flexDirection="column"
              gap="$16"
              borderColor="border.subtle"
              borderRightWidth={1}
            >
              <Box ml="$32" mt="$16">
                <Typography variant="body-small" fontWeight={700} color="content.subtle">
                  Outline
                </Typography>
              </Box>

              <Box overflow="auto" ml="$12">
                <TableOfContentsPlugin />
              </Box>
            </Box>

            <StyledRunbookEditorWrapper flexBasis={0} flexGrow={4}>
              <RunbookEditor runbookMarkdown={runbookMarkdown} />
            </StyledRunbookEditorWrapper>
          </Box>
        </LexicalComposer>
      </Box>
    </Dialog>
  );
});
