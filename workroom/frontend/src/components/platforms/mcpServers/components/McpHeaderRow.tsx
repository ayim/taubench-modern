import { FC } from 'react';
import { Box, Button, Input, Select } from '@sema4ai/components';
import { IconTrash } from '@sema4ai/icons';

type Props = {
  index: number;
  keyName: string;
  value: string;
  type: 'string' | 'secret';
  onKeyChange: (index: number, next: string) => void;
  onTypeChange: (index: number, next: 'string' | 'secret') => void;
  onValueChange: (index: number, next: string) => void;
  onRemove: (index: number) => void;
};

export const McpHeaderRow: FC<Props> = ({
  index,
  keyName,
  value,
  type,
  onKeyChange,
  onTypeChange,
  onValueChange,
  onRemove,
}) => {
  return (
    <Box display="grid" style={{ gridTemplateColumns: '1fr 160px 1fr auto', gap: '0.5rem' }}>
      <Input
        label="Header key"
        placeholder="Key"
        value={keyName}
        onChange={(e) => onKeyChange(index, e.target.value)}
      />
      <Select
        label="Type"
        items={[
          { value: 'string', label: 'Plain Text' },
          { value: 'secret', label: 'Secret' },
        ]}
        value={type}
        onChange={(selectedType) => onTypeChange(index, selectedType as 'string' | 'secret')}
      />
      <Input
        label="Header value"
        placeholder="Value"
        type={type === 'secret' ? 'password' : 'text'}
        value={value}
        onChange={(e) => onValueChange(index, e.target.value)}
      />
      <Button
        variant="ghost"
        size="small"
        icon={IconTrash}
        aria-label="Remove header"
        type="button"
        onClick={() => onRemove(index)}
      />
    </Box>
  );
};
