import { FC } from 'react';
import { useFormContext } from 'react-hook-form';
import { Box, Typography, Button, Input } from '@sema4ai/components';
import { IconPlus, IconTrash } from '@sema4ai/icons';

type Props = {
  fieldName: string;
  label: string;
  description?: string;
  isOptional: boolean;
};

export const KeyValueRecordField: FC<Props> = ({ description, fieldName, label, isOptional }) => {
  const { watch, setValue } = useFormContext();
  const values: Record<string, string> = watch(fieldName) || {};

  const entries = Object.entries(values);

  const setRecord = (newRecord: Record<string, string>) => setValue(fieldName, newRecord, { shouldDirty: true });

  const updateKey = (index: number, newKey: string) => {
    const newValues = [...entries];
    newValues[index][0] = newKey;
    setRecord(Object.fromEntries(newValues));
  };

  const updateValue = (key: string, newValue: string) => {
    const newRecord = { ...values };
    newRecord[key] = newValue;
    setRecord(newRecord);
  };

  const removeEntry = (key: string) => {
    const newRecord = { ...values };
    delete newRecord[key];
    setRecord(newRecord);
  };

  const addEntry = () => {
    let candidate = '' as string;
    if (candidate in values) {
      let index = 1;
      while (`key_${index}` in values) index += 1;
      candidate = `key_${index}`;
    }
    setRecord({ ...values, [candidate]: '' });
  };

  return (
    <Box display="flex" flexDirection="column" gap="$4">
      <Box display="flex" gap="$4" fontWeight="medium">
        {label}
        {isOptional ? <Typography color="content.subtle.light">(Optional)</Typography> : ''}
      </Box>
      {description && (
        <Typography color="content.subtle.light" mb="$12">
          {description}
        </Typography>
      )}
      {entries.map(([key, value], index) => {
        return (
          // eslint-disable-next-line react/no-array-index-key
          <Box display="flex" gap="$4" key={`${fieldName}.${index}`}>
            <Box flex="1">
              <Input value={key} onChange={(e) => updateKey(index, e.target.value)} aria-label="Key" />
            </Box>
            <Box flex="1">
              <Input value={value ?? ''} onChange={(e) => updateValue(key, e.target.value)} aria-label="Value" />
            </Box>
            <Button onClick={() => removeEntry(key)} aria-label="remove-item" icon={IconTrash} variant="ghost-subtle" />
          </Box>
        );
      })}
      <Box>
        <Button onClick={addEntry} icon={IconPlus} variant="ghost-subtle" round>
          Add
        </Button>
      </Box>
    </Box>
  );
};
