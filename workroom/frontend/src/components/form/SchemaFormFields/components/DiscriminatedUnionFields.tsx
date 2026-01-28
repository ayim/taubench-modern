/* eslint-disable no-underscore-dangle */
import { Box, Form } from '@sema4ai/components';
import { FC, useMemo } from 'react';
import { useFormContext } from 'react-hook-form';
import { z, util } from 'zod';

import { getLLMProviderIcon, snakeToCapitalCase } from '../../../helpers';
import { SelectControlled } from '../../SelectControlled';
import { SchemaFormFields } from '../index';

type Props = {
  schema:
    | z.ZodDiscriminatedUnion<z.ZodObject[], string>
    | z.ZodOptional<z.ZodDiscriminatedUnion<z.ZodObject[], string>>;
  formKeyPrefix: string;
  namePrefix: string;
};

export const DiscriminatedUnionFields: FC<Props> = ({ schema, formKeyPrefix, namePrefix }) => {
  const { def } = schema._zod;
  const definition = 'innerType' in def ? def.innerType._zod.def : def;

  // Finding the discriminator and its possible values
  const { discriminator } = definition;
  const discriminatorValues = definition.options.map((option) => {
    const discriminatorField = option.shape[discriminator];
    const fieldDef =
      'innerType' in discriminatorField.def ? discriminatorField.def.innerType.def : discriminatorField.def;
    return fieldDef.values[0];
  });
  const items = discriminatorValues.map((value) => ({
    label: snakeToCapitalCase(value),
    value,
  }));

  const name = `${formKeyPrefix}.${discriminator}`;

  const { watch, setValue } = useFormContext();
  const value = watch(name);

  // Specifically handle left-icon and label for provider field
  // Selector Icon
  const selectorIconLeft = discriminator === 'provider' && value !== undefined ? getLLMProviderIcon(value) : undefined;

  const selectorLabel = snakeToCapitalCase(
    discriminator === 'provider' ? namePrefix : `${namePrefix} ${discriminator}`,
  );

  const onClear = schema.optional()
    ? () => {
        setValue(formKeyPrefix, undefined, { shouldDirty: true });
      }
    : undefined;

  const selectOptionsSchema = useMemo(() => {
    if (!value) return null;
    const option = definition.options.find((curr) => {
      const discriminatorField = curr.shape[discriminator];
      const fieldDef =
        'innerType' in discriminatorField.def ? discriminatorField.def.innerType.def : discriminatorField.def;
      return fieldDef.values[0] === value;
    });
    return option ? util.omit(option, { [discriminator]: true }) : null;
  }, [value, definition.options, discriminator]);

  return (
    <>
      <SelectControlled
        name={name}
        label={selectorLabel}
        aria-label={selectorLabel}
        labelOptional={schema.isOptional() ? '(Optional)' : undefined}
        description={schema.description}
        iconLeft={selectorIconLeft}
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

      {!!selectOptionsSchema && (
        <Box pl="$24">
          <Form.Fieldset>
            {/* eslint-disable-next-line no-use-before-define */}
            <SchemaFormFields schema={selectOptionsSchema} formKeyPrefix={formKeyPrefix} />
            {/* eslint-disable-next-line no-use-before-define */}
            <SchemaFormFields schema={selectOptionsSchema} formKeyPrefix={formKeyPrefix} optionalFields />
          </Form.Fieldset>
        </Box>
      )}
    </>
  );
};
