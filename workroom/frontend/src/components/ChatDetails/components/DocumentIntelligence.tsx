import { useEffect, useState } from 'react';
import { Box, Link, Switch, Typography } from '@sema4ai/components';
import { IconDocumentIntelligence } from '@sema4ai/icons/logos';

import { EXTERNAL_LINKS } from '~/lib/constants';
import { useAgentDetailsContext } from './context';

export const DocumentIntelligence = () => {
  const { agent, updateAgent } = useAgentDetailsContext();
  const [state, setState] = useState<'v2' | 'v2.1' | null>(agent.extra?.document_intelligence as 'v2' | 'v2.1' | null);

  useEffect(() => {
    setState(agent.extra?.document_intelligence as 'v2' | 'v2.1' | null);
  }, [agent]);

  const onToggle = () => {
    setState(state === 'v2.1' ? null : 'v2.1');
    updateAgent({ extra: { document_intelligence: state === 'v2.1' ? null : 'v2.1' } });
  };

  return (
    <Box display="flex" flexDirection="column" gap="$8">
      <Box display="flex" alignItems="center" gap="$8">
        <IconDocumentIntelligence />
        <Typography fontWeight="medium">Document Intelligence</Typography>
        <Box ml="auto">
          <Switch aria-label="Document Intelligence" checked={state === 'v2.1'} onClick={onToggle} />
        </Box>
      </Box>
      <Typography color="content.subtle.light">
        Use Document Intelligence to analyze documents and extract information{' '}
        <Link href={EXTERNAL_LINKS.SEMANTIC_DATA_MODELS} target="_blank">
          Learn more
        </Link>
      </Typography>
    </Box>
  );
};
