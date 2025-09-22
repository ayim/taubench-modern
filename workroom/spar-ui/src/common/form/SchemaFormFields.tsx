import { FieldErrors, FieldValues, useFormContext } from 'react-hook-form';
import { z } from 'zod';

import { DiscriminatedUnionFields } from './DiscriminatedUnionFields';
import { InputControlled } from './InputControlled';
import { SelectControlled } from './SelectControlled';
import { snakeToCapitalCase } from '../helpers';

type Props = {
  descriptionAsLabel?: boolean;
  schema: z.ZodObject<z.ZodRawShape>;
  optionalFields?: boolean;
  formKeyPrefix?: string;
};

/**
 * Displays Form fields based on the provided Zod schema
 */
export const SchemaFormFields = <T extends FieldValues, K extends string>({
  descriptionAsLabel,
  optionalFields,
  formKeyPrefix,
  schema,
}: Props) => {
  const { formState, watch, setValue, register } = useFormContext();
  const fieldValues = watch(formKeyPrefix || '');

  return (Object.keys(schema.shape) as Array<K>).map((key) => {
    const { isOptional, description, _def } = schema.shape[key];
    // eslint-disable-next-line no-underscore-dangle
    const definition = 'innerType' in _def ? _def.innerType._def : _def;
    const typeName = definition.typeName as z.ZodFirstPartyTypeKind;

    if ((isOptional() && !optionalFields) || (!isOptional() && optionalFields)) {
      return null;
    }

    const fieldName = `${formKeyPrefix ? `${formKeyPrefix}.` : ''}${key}`;
    const fieldLabel = snakeToCapitalCase(
      descriptionAsLabel && description ? description : key.replace(/([A-Z])/g, ' $1').trim(),
    );
    let fieldDescription = !descriptionAsLabel ? description : undefined;

    // Workaround for zod effects, which is created by preprocessing string[] type fields
    if (typeName === z.ZodFirstPartyTypeKind.ZodEffects) {
      // eslint-disable-next-line no-underscore-dangle
      fieldDescription = _def.schema._def.description;
    }

    const error = !!fieldName.split('.').reduce<FieldErrors<T> | undefined>((acc, curr) => {
      if (acc && typeof acc === 'object') {
        return acc[curr] as FieldErrors<T>;
      }
      return undefined;
    }, formState.errors as FieldErrors<T>);

    if (typeName === z.ZodFirstPartyTypeKind.ZodNumber) {
      return (
        <InputControlled
          key={key}
          label={fieldLabel}
          fieldName={fieldName}
          type="number"
          description={fieldDescription}
          error={error}
          labelOptional={optionalFields ? '(optional)' : undefined}
        />
      );
    }

    if (typeName === z.ZodFirstPartyTypeKind.ZodBranded) {
      return (
        <InputControlled
          key={key}
          label={fieldLabel}
          fieldName={fieldName}
          type="password"
          description={fieldDescription}
          error={error}
          labelOptional={optionalFields ? '(optional)' : undefined}
        />
      );
    }

    if (typeName === z.ZodFirstPartyTypeKind.ZodEnum && 'values' in definition) {
      const enumValues = definition.values as string[];

      return (
        <SelectControlled
          key={key}
          label={fieldLabel}
          name={fieldName}
          items={enumValues.map((value) => ({
            label: value,
            value,
          }))}
          description={fieldDescription}
          error={error}
          labelOptional={optionalFields ? '(optional)' : undefined}
          onClear={() => {
            const newValues = { ...fieldValues };
            delete newValues[key];
            setValue(formKeyPrefix || '', newValues, { shouldDirty: true });
          }}
        />
      );
    }

    if (typeName === z.ZodFirstPartyTypeKind.ZodBoolean) {
      let boolValue: string | undefined;

      if (key in fieldValues) {
        boolValue = fieldValues[key] ? 'true' : 'false';
      }

      return (
        <SelectControlled
          key={key}
          label={fieldLabel}
          name={fieldName}
          items={[
            { label: 'true', value: 'true' },
            { label: 'false', value: 'false' },
          ]}
          description={fieldDescription}
          error={error}
          labelOptional={optionalFields ? '(optional)' : undefined}
          onChange={(newValue: string) => setValue(fieldName, newValue === 'true', { shouldDirty: true })}
          value={boolValue}
          onClear={() => {
            const newValues = { ...fieldValues };
            delete newValues[key];
            setValue(formKeyPrefix || '', newValues, { shouldDirty: true });
          }}
        />
      );
    }

    if (optionalFields && typeName === z.ZodFirstPartyTypeKind.ZodLiteral) {
      if (definition.value === undefined) return null;
      return (
        <input key={key} type="hidden" {...register(fieldName, { value: definition.value, shouldUnregister: true })} />
      );
    }

    if (typeName === z.ZodFirstPartyTypeKind.ZodDiscriminatedUnion) {
      return (
        <DiscriminatedUnionFields
          key={key}
          schema={schema.shape[key] as z.ZodDiscriminatedUnion<string, z.AnyZodObject[]>}
          formKeyPrefix={fieldName}
          namePrefix={key}
        />
      );
    }

    return (
      <InputControlled
        key={key}
        label={fieldLabel}
        fieldName={fieldName}
        description={fieldDescription}
        error={error}
        labelOptional={optionalFields ? '(optional)' : undefined}
      />
    );
  });
};
