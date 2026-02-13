import { ChangeEvent, KeyboardEvent, useEffect, useState } from 'react';
import { Box, Input, Typography } from '@sema4ai/components';
import { AgentIcon } from '@sema4ai/layouts';

import { UserRole, useUserRole } from '~/hooks/useUserRole';
import { useAgentDetailsContext } from './context';

export const AgentName = () => {
  const { agent, updateAgent } = useAgentDetailsContext();
  const hasAdminRole = useUserRole(UserRole.Admin);
  const [name, setName] = useState(agent.name);

  useEffect(() => {
    setName(agent.name);
  }, [agent]);

  const onChange = (e: ChangeEvent<HTMLInputElement>) => setName(e.target.value);

  const onBlur = () => {
    if (name !== agent.name) {
      updateAgent({ name });
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      onBlur();
    }
  };

  if (!hasAdminRole) {
    return null;
  }

  return (
    <Box display="flex" flexDirection="column" gap="$8">
      <Typography fontWeight="medium">Icon & Name</Typography>
      <Box display="flex" gap="$8">
        <AgentIcon mode={agent.mode} identifier={name} />
        <Box flex="1">
          <Input value={name} onBlur={onBlur} onKeyDown={onKeyDown} onChange={onChange} aria-label="Agent Name" />
        </Box>
      </Box>
    </Box>
  );
};
