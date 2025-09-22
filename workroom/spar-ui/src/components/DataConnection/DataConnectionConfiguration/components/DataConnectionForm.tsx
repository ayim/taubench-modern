import { FC, useMemo } from 'react';
import { z } from 'zod';
import {
  dataSourceConnectionConfigurationSchemaByEngine,
  type DataSourceEngineWithConnection,
  DataConnection,
  customerFacingDataSourceEngineName,
} from '@sema4ai/data-interface';
import { Form, Input } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { SchemaFormFields } from '../../../../common/form/SchemaFormFields';
import { SelectControlled } from '../../../../common/form/SelectControlled';
import { getDataConnectionIcon } from '../../components/DataConnectionIcon';

type AcceptedSchemaType = z.ZodObject<z.ZodRawShape>;
const explicitSnowflakeSchema = (
  dataSourceConnectionConfigurationSchemaByEngine.snowflake.options.find((schema) => {
    const result = (schema as AcceptedSchemaType).pick({ credential_type: true }).safeParse({
      credential_type: undefined,
    });
    return result.success;
  }) as (typeof dataSourceConnectionConfigurationSchemaByEngine)['snowflake']['options'][0]
).omit({ credential_type: true });

const extractSchemaByEngine = (engine: DataSourceEngineWithConnection): AcceptedSchemaType => {
  if (engine === 'snowflake') {
    return explicitSnowflakeSchema;
  }
  return dataSourceConnectionConfigurationSchemaByEngine[engine];
};

type Props = {
  allowEngineChange?: boolean;
};

export const CONFIGURABLE_DATA_SOURCES = Object.keys(
  dataSourceConnectionConfigurationSchemaByEngine,
) as DataSourceEngineWithConnection[];

export const DataConnectionForm: FC<Props> = ({ allowEngineChange }) => {
  const { register, watch } = useFormContext<DataConnection>();
  const { engine } = watch();

  const configSchema = useMemo(() => extractSchemaByEngine(engine), [engine]);

  return (
    <Form.Fieldset>
      <Input
        label="Name"
        {...register('name')}
        description="Enter a unique name for the Connection Details"
        autoFocus
      />
      <Input
        label="Description"
        {...register('description')}
        description="Enter a description for the Connection Details"
      />
      <SelectControlled
        name="engine"
        label="Engine"
        iconLeft={getDataConnectionIcon(engine)}
        items={CONFIGURABLE_DATA_SOURCES.map((value) => ({
          label: customerFacingDataSourceEngineName(value),
          value,
        }))}
        disabled={!allowEngineChange}
      />
      <SchemaFormFields<DataConnection, keyof DataConnection['configuration']>
        schema={configSchema}
        formKeyPrefix="configuration"
      />
      <SchemaFormFields<DataConnection, keyof DataConnection['configuration']>
        schema={configSchema}
        formKeyPrefix="configuration"
        optionalFields
      />
    </Form.Fieldset>
  );
};
