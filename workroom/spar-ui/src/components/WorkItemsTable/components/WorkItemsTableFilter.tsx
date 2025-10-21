import { Filter, FilterGroup, ToggleInputButton } from '@sema4ai/components';
import { IconSearch } from '@sema4ai/icons';
import { FC, useMemo } from 'react';

import { WORK_ITEM_STATUS_CONFIG, WORK_ITEM_STATUS_VALUES } from '../../../constants/workItemStatus';

type TableFilterProps = {
  search: string;
  onSearchChange: (value: string) => void;
  filters: Record<'Status' | 'AgentName', string[]>;
  onFiltersChange: (filters: Record<'Status' | 'AgentName', string[]>) => void;
  agentNames: string[];
};

export const WorkItemsTableFilter: FC<TableFilterProps> = ({
  search,
  onSearchChange,
  filters,
  onFiltersChange,
  agentNames,
}) => {
  const stateOptions = useMemo<Record<'Status' | 'AgentName', FilterGroup>>(
    () => ({
      Status: {
        label: 'Status',
        searchable: true,
        options: WORK_ITEM_STATUS_VALUES.map((status) => ({
          label: WORK_ITEM_STATUS_CONFIG[status]?.label || status,
          value: status,
          itemType: 'checkbox',
        })),
      },
      AgentName: {
        label: 'Agent Name',
        searchable: true,
        options: agentNames.map((agentName) => ({
          label: agentName,
          value: agentName,
          itemType: 'radio',
        })),
      },
    }),
    [agentNames],
  );

  return (
    <Filter
      contentBefore={
        <ToggleInputButton
          iconLeft={IconSearch}
          placeholder="Search by Work Item ID or Name"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          aria-label="Search"
          onClear={() => onSearchChange('')}
          buttonVariant="ghost-subtle"
          round
        />
      }
      onChange={onFiltersChange}
      options={stateOptions}
      values={filters}
    />
  );
};

