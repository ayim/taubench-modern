import { FC, useEffect, useMemo } from 'react';
import { z } from 'zod';
import {
  dataSourceConnectionConfigurationSchemaByEngine,
  type DataSourceEngineWithConnection,
  DataConnection,
  customerFacingDataSourceEngineName,
} from '@sema4ai/data-interface';
import { Form, Input } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { SchemaFormFields } from '~/components/form/SchemaFormFields';
import { SelectControlled } from '~/components/form/SelectControlled';
import { getDataConnectionIcon } from '../../components/DataConnectionIcon';
import { SnowflakeCredentialField } from './SnowflakeCredentialField';

type Props = {
  allowEngineChange?: boolean;
  supportedEngines?: DataConnection['engine'][];
  snowflakeLinkedUser?: string;
};

export const CONFIGURABLE_DATA_SOURCES = Object.keys(
  dataSourceConnectionConfigurationSchemaByEngine,
) as DataSourceEngineWithConnection[];

export const DataConnectionForm: FC<Props> = ({ allowEngineChange, supportedEngines, snowflakeLinkedUser }) => {
  const { register, watch, setValue } = useFormContext<DataConnection>();
  const { engine, configuration } = watch();

  const snowflakeCredentialType =
    configuration && 'credential_type' in configuration ? configuration.credential_type : undefined;

  const configSchema = useMemo(() => {
    if (engine === 'snowflake') {
      const snowflakeSchema = dataSourceConnectionConfigurationSchemaByEngine.snowflake.options.find((schema) => {
        const result = (schema as z.ZodObject<z.ZodRawShape>).pick({ credential_type: true }).safeParse({
          credential_type: snowflakeCredentialType || 'custom-key-pair',
        });

        return result.success;
      });

      return snowflakeSchema as (typeof dataSourceConnectionConfigurationSchemaByEngine)['snowflake']['options'][0];
    }

    return dataSourceConnectionConfigurationSchemaByEngine[engine];
  }, [engine, snowflakeCredentialType]);

  const engineOptions = useMemo(() => {
    const engines = supportedEngines || CONFIGURABLE_DATA_SOURCES;
    return engines.map((value) => ({
      label: customerFacingDataSourceEngineName(value),
      value,
    }));
  }, [supportedEngines]);

  const customFields = useMemo(() => {
    return [
      {
        fieldName: 'configuration.credential_type',
        component: SnowflakeCredentialField,
        props: { snowflakeLinkedUser },
      },
    ];
  }, [snowflakeLinkedUser]);

  useEffect(() => {
    if (engine === 'snowflake' && !snowflakeCredentialType) {
      const setting = snowflakeLinkedUser ? 'linked' : 'custom-key-pair';
      setValue('configuration.credential_type', setting);
    }
  }, [engine, snowflakeLinkedUser, snowflakeCredentialType]);

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
        items={engineOptions}
        disabled={!allowEngineChange}
      />
      <SchemaFormFields<DataConnection, keyof DataConnection['configuration']>
        schema={configSchema}
        formKeyPrefix="configuration"
        customFields={customFields}
      />
      <SchemaFormFields<DataConnection, keyof DataConnection['configuration']>
        schema={configSchema}
        formKeyPrefix="configuration"
        customFields={customFields}
        optionalFields
      />
    </Form.Fieldset>
  );
};
