/* eslint-disable camelcase */
import { useMemo } from 'react';
import { useFormContext } from 'react-hook-form';
import { Select } from '@sema4ai/components';

import { useAgentArchitecturesQuery } from '~/queries/agents';
import { AgentDetailsSchema } from './context';

export const Architecture = () => {
  const { data: architectures, isLoading } = useAgentArchitecturesQuery({});
  const { watch, setValue } = useFormContext<AgentDetailsSchema>();
  const { agent_architecture } = watch();

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
      setValue('agent_architecture', { name: architecture.name, version: architecture.version }, { shouldDirty: true });
    }
  };

  return (
    <Select
      value={agent_architecture?.name}
      items={items}
      disabled={isLoading}
      label="Architecture"
      onChange={onChange}
      description="Choose how your agent will reason, plan, and act."
    />
  );
};
