import { FC } from 'react';
import { Box, Typography, Table } from '@sema4ai/components';

const formatLabel = (key: string): string => key.replace(/_/g, ' ');
const isPrimitive = (value: unknown): boolean =>
  value === null || ['string', 'number', 'boolean'].includes(typeof value);

/**
 * Main check to see if this is can be displayed as table, key value pair or primitive instead
 */
const isArrayForTable = (value: unknown[]): boolean => {
  if (value.length === 0) return false;

  const allItemsAreObjects = value.every((item) => item !== null && typeof item === 'object' && !Array.isArray(item));
  if (!allItemsAreObjects) return false;

  const firstItem = value[0] as Record<string, unknown>;
  const firstKeyCount = Object.keys(firstItem).length;
  const allHaveSameKeyCount = value.every((item) => {
    return Object.keys(item as Record<string, unknown>).length === firstKeyCount;
  });
  if (!allHaveSameKeyCount) return false;

  return value.every((item) => {
    const obj = item as Record<string, unknown>;
    return Object.values(obj).every((val) => isPrimitive(val));
  });
};

const TableFromArray: FC<{ items: unknown[] }> = ({ items }) => {
  if (items.length === 0) return null;

  const firstItem = items[0];
  if (!firstItem || typeof firstItem !== 'object' || Array.isArray(firstItem)) {
    return null;
  }

  const columnKeys = Object.keys(firstItem);
  if (columnKeys.length === 0) return null;

  const columns = columnKeys.map((key) => ({
    id: key,
    title: formatLabel(key),
  }));

  const rows = items.map((item) => {
    const row: Record<string, string> = {};
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      columnKeys.forEach((key) => {
        const cellValue = (item as Record<string, unknown>)[key];
        row[key] = cellValue !== null && cellValue !== undefined ? String(cellValue) : '';
      });
    }
    return row;
  });

  return (
    <Box marginBottom="$16">
      <Table columns={columns} data={rows} />
    </Box>
  );
};

const PrimitiveValue: FC<{ label?: string; value: unknown }> = ({ label, value }) => {
  const displayValue = String(value);
  const isEmpty = displayValue.trim().length === 0;

  return (
    <Box marginBottom="$8">
      {label && (
        <Typography fontSize="$12" color="content.subtle" marginBottom="$4">
          {formatLabel(label)}
        </Typography>
      )}
      {!isEmpty && (
        <Typography fontSize="$14" style={{ whiteSpace: 'pre-wrap' }}>
          {displayValue}
        </Typography>
      )}
    </Box>
  );
};

const SectionHeader: FC<{ title: string }> = ({ title }) => (
  <Box marginTop="$16" marginBottom="$8">
    <Typography fontSize="$16" fontWeight="bold" color="content.primary">
      {formatLabel(title)}
    </Typography>
  </Box>
);

const DataRenderer: FC<{ value: unknown; label?: string }> = ({ value, label }) => {
  const isArrayData = Array.isArray(value);
  if (isArrayData && isArrayForTable(value)) {
    return (
      <>
        {label && <SectionHeader title={label} />}
        <TableFromArray items={value} />
      </>
    );
  }

  if (isArrayData && value.length === 0) {
    return label ? <PrimitiveValue label={label} value="" /> : null;
  }

  if (isArrayData) {
    return (
      <>
        {label && <SectionHeader title={label} />}
        {value.map((item, index) => {
          const itemKey = `${label || 'item'}-${index}`;
          return <DataRenderer key={itemKey} value={item} />;
        })}
      </>
    );
  }

  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);

    if (entries.length === 0) {
      return label ? <PrimitiveValue label={label} value="" /> : null;
    }

    return (
      <>
        {label && <SectionHeader title={label} />}
        {entries.map(([key, nestedValue]) => {
          if (!key) return null;
          return <DataRenderer key={key} value={nestedValue} label={key} />;
        })}
      </>
    );
  }

  if (isPrimitive(value)) {
    return <PrimitiveValue label={label} value={value} />;
  }

  return null;
};

export const ExtractedDataRenderer: FC<{ data: unknown }> = ({ data }) => (
  <Box display="flex" flexDirection="column">
    <DataRenderer value={data} />
  </Box>
);
