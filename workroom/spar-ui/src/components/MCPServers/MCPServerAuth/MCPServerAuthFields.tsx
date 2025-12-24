import { FC } from 'react';
import { Controller, useFormContext } from 'react-hook-form';
import { Box, Select } from '@sema4ai/components';
import { MCPServerClientCredentialsFields } from './MCPServerClientCredentialsFields';
import { mcpAuthenticationTypeSelectItems } from '../schemas/mcpAuthSchema';

type MCPServerAuthFieldsProps = {
  disabled?: boolean;
  /**
   * Field name prefix for client credentials form registration.
   * - Use 'client_credentials' for nested form schemas (default)
   * - Use '' (empty string) for flat form schemas where fields are at root level
   */
  clientCredentialsFieldPrefix?: string;
};

export const MCPServerAuthFields: FC<MCPServerAuthFieldsProps> = ({ disabled, clientCredentialsFieldPrefix }) => {
  const { control, watch } = useFormContext();
  const authenticationType = watch('authentication_type');

  return (
    <Box display="flex" flexDirection="column" gap="$12">
      <Controller
        name="authentication_type"
        control={control}
        render={({ field }) => (
          <Select
            label="Authentication"
            items={mcpAuthenticationTypeSelectItems}
            value={field.value || 'none'}
            onChange={field.onChange}
            disabled={disabled}
          />
        )}
      />

      {/* Client Credentials Flow - show credential fields */}
      {authenticationType === 'oauth2-client-credentials' && (
        <MCPServerClientCredentialsFields disabled={disabled} fieldPrefix={clientCredentialsFieldPrefix} />
      )}

      {/* Authorization Code Flow - placeholder for login button */}
      {/* TODO https://linear.app/sema4ai/issue/ENG-57/implement-oauth2-authorization-code-flow-ui-for-mcp-servers  */}
      {/* Implement Authorization Code Flow UI when backend is ready. */}
      {authenticationType === 'oauth2-authorization-code' && (
        <Box
          display="flex"
          flexDirection="column"
          gap="$8"
          p="$16"
          borderRadius="$8"
          backgroundColor="background.subtle"
          borderColor="border.primary"
        >
          <Box>
            OAuth2 Authorization Code Flow allows users to authenticate with the MCP server. This feature is coming
            soon.
          </Box>
        </Box>
      )}
    </Box>
  );
};
