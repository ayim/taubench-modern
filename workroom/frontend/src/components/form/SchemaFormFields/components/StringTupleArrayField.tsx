import { FC } from 'react';
import { useFormContext } from 'react-hook-form';
import { Box, Button, Typography, Input } from '@sema4ai/components';
import { IconPlus, IconTrash } from '@sema4ai/icons';

type Props = {
  fieldName: string;
  label: string;
  description?: string;
  isOptional: boolean;
};

export const StringTupleArrayField: FC<Props> = ({ description, fieldName, label, isOptional }) => {
  const { watch, register, setValue } = useFormContext();
  const values: Array<[string, string]> = watch(fieldName) || [];

  return (
    <Box display="flex" flexDirection="column" gap="$4">
      <Box display="flex" gap="$4" fontWeight="medium">
        {label}
        {isOptional ? <Typography color="content.subtle.light"> (Optional)</Typography> : ''}
      </Box>
      {description && (
        <Typography color="content.subtle.light" mb="$12">
          {description}
        </Typography>
      )}
      {values.map((_, index) => {
        return (
          // eslint-disable-next-line react/no-array-index-key
          <Box display="flex" gap="$8" key={`${fieldName}.${index}`}>
            <Box flex="1">
              <Input {...register(`${fieldName}.${index}.0`)} aria-label="Key" />
            </Box>
            <Box flex="1">
              <Input {...register(`${fieldName}.${index}.1`)} aria-label="Value" />
            </Box>
            <Button
              onClick={() =>
                setValue(
                  fieldName,
                  values.filter((__, i) => i !== index),
                  { shouldDirty: true },
                )
              }
              aria-label="remove-item"
              icon={IconTrash}
              variant="ghost-subtle"
            />
          </Box>
        );
      })}
      <Box>
        <Button
          onClick={() => setValue(fieldName, [...values, ['', '']], { shouldDirty: true })}
          icon={IconPlus}
          variant="ghost-subtle"
          round
        >
          Add
        </Button>
      </Box>
    </Box>
  );
};
