import { FC } from 'react';
import { FieldErrors, FieldValues, useFormContext } from 'react-hook-form';
import { z } from 'zod';
import { CustomSchemaType, dataSourcesZodRegistry } from '@sema4ai/data-interface';

import { InputControlled } from '../InputControlled';
import { SelectControlled } from '../SelectControlled';
import { snakeToCapitalCase } from '../../helpers';
import { KeyValueRecordField } from './components/KeyValueRecordField';
import { StringTupleArrayField } from './components/StringTupleArrayField';
import { DiscriminatedUnionFields } from './components/DiscriminatedUnionFields';

type Props<K extends string> = {
  /**
   * The Zod schema to render form fields for
   */
  schema: z.ZodObject<Record<K, z.ZodTypeAny>>;
  /**
   * If true, renders optional fields only, otherwise renders required fields only
   */
  optionalFields?: boolean;
  /**
   * The prefix to use for the form for nested fields
   * @ignore
   */
  formKeyPrefix?: string;
  /**
   * Custom fields to render based on field name
   */
  customFields?: { fieldName: string; component: FC; props?: Record<string, unknown> }[];
};

/**
 * Renders react-hook-form connected form fields based on a Zod schema
 */
export const SchemaFormFields = <T extends FieldValues, K extends string>({
  optionalFields,
  formKeyPrefix,
  schema,
  customFields,
}: Props<K>) => {
  const { formState, watch, setValue } = useFormContext();

  const fieldValues = watch(formKeyPrefix || '');

  return (Object.keys(schema.shape) as Array<K>).map((key) => {
    const fieldSchema = schema.shape[key];

    const isOptional = schema.shape[key].def.type === 'optional';

    if ((isOptional && !optionalFields) || (!isOptional && optionalFields)) {
      return null;
    }

    const fieldDefinition =
      'innerType' in fieldSchema.def ? (fieldSchema.def.innerType as z.core.$ZodTypeDef) : fieldSchema.def;

    const customSchemaType =
      'innerType' in fieldSchema.def
        ? dataSourcesZodRegistry.get(fieldSchema.def.innerType as z.core.$ZodType<unknown>)
        : dataSourcesZodRegistry.get(fieldSchema);

    const { description } = fieldSchema;

    const fieldName = `${formKeyPrefix ? `${formKeyPrefix}.` : ''}${key}`;

    const error = !!fieldName.split('.').reduce<FieldErrors<T> | undefined>((acc, curr) => {
      if (acc && typeof acc === 'object') {
        return acc[curr] as FieldErrors<T>;
      }
      return undefined;
    }, formState.errors as FieldErrors<T>);

    const customField = customFields?.find((curr) => curr.fieldName === fieldName);

    if (customField) {
      const { component: CustomField, props } = customField;
      return <CustomField {...props} />;
    }

    if (customSchemaType?.customSchemaType) {
      if (customSchemaType?.customSchemaType === CustomSchemaType.Secret) {
        return (
          <InputControlled
            key={key}
            label={snakeToCapitalCase(key)}
            fieldName={fieldName}
            type="password"
            description={description}
            error={error}
            labelOptional={isOptional ? '(optional)' : undefined}
          />
        );
      }

      if (customSchemaType?.customSchemaType === CustomSchemaType.KeyValueRecord) {
        return (
          <KeyValueRecordField
            key={key}
            fieldName={fieldName}
            label={snakeToCapitalCase(key)}
            description={description}
            isOptional={isOptional}
          />
        );
      }

      if (customSchemaType?.customSchemaType === CustomSchemaType.StringTupleArray) {
        return (
          <StringTupleArrayField
            key={key}
            fieldName={fieldName}
            label={snakeToCapitalCase(key)}
            description={description}
            isOptional={isOptional}
          />
        );
      }

      return null;
    }

    if (fieldDefinition.type === 'string') {
      return (
        <InputControlled
          key={key}
          label={snakeToCapitalCase(key)}
          fieldName={fieldName}
          description={description}
          error={error}
          labelOptional={optionalFields ? '(optional)' : undefined}
        />
      );
    }

    if (fieldDefinition.type === 'boolean') {
      let boolValue: string | undefined;

      if (key in fieldValues) {
        boolValue = fieldValues[key] ? 'true' : 'false';
      }

      return (
        <SelectControlled
          key={key}
          label={snakeToCapitalCase(key)}
          name={fieldName}
          items={[
            { label: 'true', value: 'true' },
            { label: 'false', value: 'false' },
          ]}
          description={description}
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

    if (fieldDefinition.type === 'number') {
      return (
        <InputControlled
          key={key}
          label={snakeToCapitalCase(key)}
          fieldName={fieldName}
          type="number"
          description={description}
          error={error}
          labelOptional={optionalFields ? '(optional)' : undefined}
        />
      );
    }

    if (fieldDefinition.type === 'enum' && 'options' in fieldDefinition) {
      const enumValues = fieldDefinition.options as string[];
      return (
        <SelectControlled
          key={key}
          label={snakeToCapitalCase(key)}
          name={fieldName}
          items={enumValues.map((value) => ({
            label: value,
            value,
          }))}
          description={description}
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

    if (fieldDefinition.type === 'union') {
      return (
        <DiscriminatedUnionFields
          key={key}
          schema={schema.shape[key] as z.ZodDiscriminatedUnion<z.ZodObject[], string>}
          formKeyPrefix={fieldName}
          namePrefix={key}
        />
      );
    }

    return (
      <InputControlled
        key={key}
        label={snakeToCapitalCase(key)}
        fieldName={fieldName}
        description={description}
        error={error}
        labelOptional={optionalFields ? '(optional)' : undefined}
      />
    );
  });
};
