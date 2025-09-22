import { Box, Form } from '@sema4ai/components';
import { FC } from 'react';
import { useFormContext } from 'react-hook-form';
import { z } from 'zod';

import { snakeToCapitalCase } from '../helpers';
import { SchemaFormFields } from './SchemaFormFields';
import { SelectControlled } from './SelectControlled';

export const DiscriminatedUnionFields: FC<{
  schema:
    | z.ZodDiscriminatedUnion<string, z.AnyZodObject[]>
    | z.ZodOptional<z.ZodDiscriminatedUnion<string, z.AnyZodObject[]>>;
  formKeyPrefix: string;
  namePrefix: string;
}> = ({ schema, formKeyPrefix, namePrefix }) => {
  // eslint-disable-next-line no-underscore-dangle
  const def = schema._def;
  // eslint-disable-next-line no-underscore-dangle
  const definition = 'innerType' in def ? def.innerType._def : def;

  // Finding the discriminator and its possiblevalues
  const { discriminator } = definition;
  const discriminatorValues = Array.from(definition.optionsMap.keys()) as string[];
  const items = discriminatorValues.map((value) => ({
    label: snakeToCapitalCase(value),
    value,
  }));

  const name = `${formKeyPrefix}.${discriminator}`;

  const { watch, setValue } = useFormContext();
  const value = watch(name);

  const selectorLabel = snakeToCapitalCase(
    discriminator === 'provider' ? namePrefix : `${namePrefix} ${discriminator}`,
  );

  const onClear = schema.isOptional()
    ? () => {
        setValue(formKeyPrefix, undefined, { shouldDirty: true });
      }
    : undefined;

  // Schema with other fields except discriminator
  const optionSchema = definition.optionsMap.get(value)?.omit({ [discriminator]: true });

  return (
    <>
      <SelectControlled
        name={name}
        label={selectorLabel}
        aria-label={selectorLabel}
        labelOptional={schema.isOptional() ? '(Optional)' : undefined}
        description={def.description}
        items={items}
        onClear={onClear}
        onMounted={() => {
          if (!value) {
            // for optional field, completly set it as undefined
            if (schema.isOptional()) setValue(formKeyPrefix, undefined, { shouldDirty: false });
            // for non-optional field, set the first value
            else if (!schema.isOptional()) setValue(name, discriminatorValues[0], { shouldDirty: false });
          }
        }}
      />

      {!!optionSchema && (
        <Box pl="$24">
          <Form.Fieldset>
            <SchemaFormFields schema={optionSchema} formKeyPrefix={formKeyPrefix} />
            <SchemaFormFields schema={optionSchema} formKeyPrefix={formKeyPrefix} optionalFields />
          </Form.Fieldset>
        </Box>
      )}
    </>
  );
};
