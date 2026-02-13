import { useMemo } from 'react';
import { Select } from '@sema4ai/components';

import { useAgentArchitecturesQuery } from '~/queries/agents';
import { useAgentDetailsContext } from './context';

export const Architecture = () => {
  const { data: architectures, isLoading } = useAgentArchitecturesQuery({});
  const { agent, updateAgent } = useAgentDetailsContext();

  const items = useMemo(() => {
    return (
      architectures?.map((architecture) => ({
        value: architecture.name,
        label: architecture.name,
        description: architecture.summary,
      })) || []
    );
  }, [architectures]);

  const onChange = (value: string) => {
    const architecture = architectures?.find((curr) => curr.name === value);
    if (architecture) {
      updateAgent({ agent_architecture: { name: architecture.name, version: architecture.version } });
    }
  };

  return (
    <Select
      value={agent.agent_architecture?.name}
      items={items}
      disabled={isLoading}
      label="Architecture"
      onChange={onChange}
      description="Choose how your agent will reason, plan, and act."
    />
  );
};
