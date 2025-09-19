import { Select } from '@sema4ai/components';
import { FC, useMemo } from 'react';
import { DataSourceItem } from './DataConnectionRow';

type DataConnectionFilterProps = {
  dataSources: DataSourceItem[];
  providerFilter: string;
  onProviderFilterChange: (provider: string) => void;
};

export const DataConnectionFilter: FC<DataConnectionFilterProps> = ({
  dataSources,
  providerFilter,
  onProviderFilterChange,
}) => {
  const providerOptions = useMemo(() => {
    const uniqueProviders = Array.from(new Set(dataSources.map(item => item.engine)));
    return [
      { value: 'all', label: 'All providers' },
      ...uniqueProviders.map((provider) => ({
        value: provider,
        label: provider.charAt(0).toUpperCase() + provider.slice(1),
      })),
    ];
  }, [dataSources]);

  return (
    <Select
      aria-label="Provider filter"
      items={providerOptions}
      value={providerFilter}
      onChange={onProviderFilterChange}
    />
  );
};

export type { DataConnectionFilterProps };
