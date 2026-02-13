import { useEffect, useState } from 'react';
import { Box, Link, Switch, Typography } from '@sema4ai/components';
import { IconDataFrames } from '@sema4ai/icons/logos';

import { EXTERNAL_LINKS } from '~/lib/constants';
import { useAgentDetailsContext } from './context';

export const DataFrames = () => {
  const { agent, updateAgent } = useAgentDetailsContext();
  const [state, setState] = useState<boolean>(
    typeof agent.extra?.enable_data_frames === 'boolean' ? agent.extra?.enable_data_frames : true,
  );

  useEffect(() => {
    setState(typeof agent.extra?.enable_data_frames === 'boolean' ? agent.extra?.enable_data_frames : true);
  }, [agent]);

  const onToggle = () => {
    setState(!state);
    updateAgent({ extra: { enable_data_frames: !state } });
  };

  return (
    <Box display="flex" flexDirection="column" gap="$8">
      <Box display="flex" alignItems="center" gap="$8">
        <IconDataFrames />
        <Typography fontWeight="medium">Data Frames</Typography>
        <Box ml="auto">
          <Switch aria-label="Data Frames" checked={state} onClick={onToggle} />
        </Box>
      </Box>
      <Typography color="content.subtle.light">
        Use Data Frames to store and manage data in a structured format.{' '}
        <Link href={EXTERNAL_LINKS.DATA_FRAMES} target="_blank">
          Learn more
        </Link>
      </Typography>
    </Box>
  );
};
