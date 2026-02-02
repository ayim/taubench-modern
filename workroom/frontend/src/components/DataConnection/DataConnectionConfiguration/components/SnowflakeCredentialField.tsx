import { FC } from 'react';
import { useFormContext } from 'react-hook-form';
import { Select, SelectItem } from '@sema4ai/components';

type Props = {
  snowflakeLinkedUser?: string;
};

enum SnowflakeCredentialType {
  Linked = 'linked',
  KeyPair = 'custom-key-pair',
  ProgrammaticAccessToken = 'programmatic-access-token',
  UsernamePassword = 'password',
}

const FIELD_NAME = 'configuration.credential_type';

/**
 * Custom field to render the Snowflake credential type select
 */
export const SnowflakeCredentialField: FC<Props> = ({ snowflakeLinkedUser }) => {
  const { watch, setValue, formState } = useFormContext();
  const value = watch(FIELD_NAME);
  const error = formState.errors[FIELD_NAME];

  const items = [
    { label: 'Key Pair', value: SnowflakeCredentialType.KeyPair },
    { label: 'Programmatic Access Token (PAT)', value: SnowflakeCredentialType.ProgrammaticAccessToken },
    { label: 'Username & Password (Legacy)', value: SnowflakeCredentialType.UsernamePassword },
    ...(snowflakeLinkedUser
      ? [{ label: `Linked Account ${snowflakeLinkedUser}`, value: SnowflakeCredentialType.Linked }]
      : []),
  ] as SelectItem[];

  return (
    <Select
      label="Credentials"
      value={value}
      error={error?.message as string}
      onChange={(newValue) => {
        setValue(FIELD_NAME, newValue, { shouldDirty: true });
      }}
      items={items}
    />
  );
};
