import { FC } from 'react';
import { useFormContext } from 'react-hook-form';
import { Box, Input } from '@sema4ai/components';
import { InputControlled } from '~/components/form/InputControlled';

type MCPServerClientCredentialsFieldsProps = {
  disabled?: boolean;
  /**
   * Field name prefix for form registration.
   * - Use 'client_credentials' for nested form schemas (e.g., 'client_credentials.token_endpoint')
   * - Use '' (empty string) for flat form schemas (e.g., 'token_endpoint')
   * @default 'client_credentials'
   */
  fieldPrefix?: string;
};

export const MCPServerClientCredentialsFields: FC<MCPServerClientCredentialsFieldsProps> = ({
  disabled,
  fieldPrefix = 'client_credentials',
}) => {
  const {
    register,
    formState: { errors },
  } = useFormContext();

  const getFieldName = (field: string) => (fieldPrefix ? `${fieldPrefix}.${field}` : field);

  const getFieldError = (field: string): string | undefined => {
    if (fieldPrefix) {
      const nestedErrors = errors[fieldPrefix] as Record<string, { message?: string }> | undefined;
      return nestedErrors?.[field]?.message;
    }
    const fieldError = errors[field] as { message?: string } | undefined;
    return fieldError?.message;
  };

  return (
    <Box display="flex" flexDirection="column" gap="$16">
      <Input
        label="Token Endpoint"
        {...register(getFieldName('endpoint'))}
        error={getFieldError('endpoint')}
        placeholder="https://auth.example.com/oauth/token"
        description="The OAuth2 token endpoint URL"
        disabled={disabled}
      />

      <Box display="grid" gridTemplateColumns="1fr 1fr" gap="$8">
        <Input
          label="Client ID"
          {...register(getFieldName('client_id'))}
          error={getFieldError('client_id')}
          placeholder="Enter client ID"
          autoComplete="off"
          disabled={disabled}
        />

        <InputControlled
          fieldName={getFieldName('client_secret')}
          label="Client Secret"
          placeholder="Enter client secret"
          type="password"
          autoComplete="new-password"
          disabled={disabled}
        />
      </Box>

      <Input
        label="Scopes (optional)"
        {...register(getFieldName('scope'))}
        error={getFieldError('scope')}
        placeholder="openid profile email"
        description="Space-separated list of OAuth2 scopes"
        disabled={disabled}
      />
    </Box>
  );
};
