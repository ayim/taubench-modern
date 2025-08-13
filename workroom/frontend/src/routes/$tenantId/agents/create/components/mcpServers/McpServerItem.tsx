import { FC, useState } from 'react';
import { Box, Input, Typography, Form, Button, Select } from '@sema4ai/components';
import { IconPlus, IconTrash } from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';
import { PackageCard } from '@sema4ai/layouts';
import { AgentDeploymentFormSchema, MCPServerSettings } from '../context';
import { McpHeaderSecretInput } from './McpHeaderSecretInput';

type Props = {
  index: number;
  mcpServer: MCPServerSettings;
};

export const McpServerItem: FC<Props> = ({ index, mcpServer }) => {
  const {
    register,
    watch,
    getValues,
    setValue,
    trigger,
    formState: { errors },
  } = useFormContext<AgentDeploymentFormSchema>();

  const mcpServerSettings = watch(`mcpServerSettings.${index}`);
  const [editingKeys, setEditingKeys] = useState<Record<string, string>>({});

  // Secrets integration not available yet; provide empty list and not-loading state
  const secrets: Array<{ id: string; name: string }> | undefined = [];
  const isLoadingSecrets = false;

  const headers = mcpServerSettings?.headers || {};
  const headerEntries = Object.entries(headers);

  const typeOptions = [
    { label: 'Plain Text', value: 'string' },
    { label: 'Secret', value: 'secret' },
  ];

  const getFieldError = (fieldName: string) => {
    const serverErrors = errors.mcpServerSettings?.[index];
    if (!serverErrors || typeof serverErrors !== 'object') return undefined;

    const fieldError = (serverErrors as Record<string, { message?: string }>)[fieldName];
    return fieldError?.message;
  };

  const updateMcpServerSettings = async (updater: (settings: MCPServerSettings) => MCPServerSettings) => {
    const currentSettings = getValues('mcpServerSettings') || [];
    const updatedSettings = [...currentSettings];
    if (updatedSettings[index]) {
      updatedSettings[index] = updater(updatedSettings[index]);
      setValue('mcpServerSettings', updatedSettings, { shouldValidate: true, shouldDirty: true });
      await trigger(`mcpServerSettings.${index}`);
    }
  };

  const createHeaderValue = (
    type: 'string' | 'secret',
    currentHeader?: NonNullable<MCPServerSettings['headers']>[string],
    value = '',
  ) => {
    const baseValue = { type: 'string' as const, value };

    if (type === 'secret') {
      return {
        type: 'secret' as const,
        value: baseValue,
        description: currentHeader?.description || null,
      };
    }

    return {
      type: 'string' as const,
      value: baseValue,
      description: currentHeader?.description || null,
    };
  };

  const addNewHeader = () =>
    updateMcpServerSettings((settings) => ({
      ...settings,
      headers: {
        ...settings.headers,
        '': createHeaderValue('string'),
      },
    }));

  const removeHeader = (key: string) =>
    updateMcpServerSettings((settings) => ({
      ...settings,
      headers: Object.fromEntries(Object.entries(settings.headers || {}).filter(([k]) => k !== key)),
    }));

  const updateHeaderKey = async (oldKey: string, newKey: string) => {
    if (oldKey === newKey) return;

    await updateMcpServerSettings((settings) => {
      const currentHeaders = settings.headers || {};
      const headerValue = currentHeaders[oldKey];
      const newHeaders = Object.fromEntries(Object.entries(currentHeaders).filter(([k]) => k !== oldKey));

      if (newKey.trim()) {
        newHeaders[newKey] = headerValue;
      }

      return { ...settings, headers: newHeaders };
    });
  };

  const updateHeaderValue = (key: string, value: string) =>
    updateMcpServerSettings((settings) => {
      const currentHeader = settings.headers?.[key];
      if (!currentHeader) return settings;

      return {
        ...settings,
        headers: {
          ...settings.headers,
          [key]: {
            ...currentHeader,
            value: { type: 'string' as const, value },
          },
        },
      };
    });

  const updateHeaderType = (key: string, type: 'string' | 'secret') =>
    updateMcpServerSettings((settings) => {
      const currentHeader = settings.headers?.[key];
      const currentValue = currentHeader?.value?.type === 'string' ? currentHeader.value.value : '';

      return {
        ...settings,
        headers: {
          ...settings.headers,
          [key]: createHeaderValue(type, currentHeader, currentValue),
        },
      };
    });

  const updateHeaderSecretId = (key: string, secretId: string) =>
    updateMcpServerSettings((settings) => {
      const currentHeader = settings.headers?.[key];
      if (!currentHeader || (currentHeader.type !== 'secret' && currentHeader.type !== 'oauth2-secret')) {
        return settings;
      }

      return {
        ...settings,
        headers: {
          ...settings.headers,
          [key]: {
            ...currentHeader,
            value: { type: 'secret' as const, secretID: secretId },
          },
        },
      };
    });

  const updateHeaderSecretValue = (key: string, value: string) =>
    updateMcpServerSettings((settings) => {
      const currentHeader = settings.headers?.[key];
      if (!currentHeader || (currentHeader.type !== 'secret' && currentHeader.type !== 'oauth2-secret')) {
        return settings;
      }

      return {
        ...settings,
        headers: {
          ...settings.headers,
          [key]: {
            ...currentHeader,
            value: { type: 'string' as const, value },
          },
        },
      };
    });

  const resetHeaderToValue = (key: string) =>
    updateMcpServerSettings((settings) => {
      const currentHeader = settings.headers?.[key];
      if (!currentHeader || (currentHeader.type !== 'secret' && currentHeader.type !== 'oauth2-secret')) {
        return settings;
      }

      return {
        ...settings,
        headers: {
          ...settings.headers,
          [key]: {
            ...currentHeader,
            value: { type: 'string' as const, value: '' },
          },
        },
      };
    });

  const handleKeyInputChange = (originalKey: string, newValue: string) => {
    setEditingKeys((prev) => ({
      ...prev,
      [originalKey]: newValue,
    }));
  };

  const handleKeyInputBlur = async (originalKey: string) => {
    const newKey = editingKeys[originalKey];
    if (newKey !== undefined) {
      await updateHeaderKey(originalKey, newKey);
      setEditingKeys((prev) => {
        const updated = { ...prev };
        delete updated[originalKey];
        return updated;
      });
    }
  };

  if (!mcpServerSettings) {
    return null;
  }

  return (
    <Box p="$0" display="flex" flexDirection="column" gap="$16">
      <PackageCard title={mcpServer.name} description={null} version={null}>
        <Box display="flex" justifyContent="flex-end" mb="$8">
          <Button
            variant="outline"
            size="small"
            icon={IconTrash}
            aria-label="Remove MCP server"
            onClick={async () => {
              const current = getValues('mcpServerSettings') || [];
              const next = current.filter((_: unknown, i: number) => i !== index);
              setValue('mcpServerSettings', next, { shouldDirty: true, shouldValidate: true });
              await trigger('mcpServerSettings');
            }}
          >
            Remove
          </Button>
        </Box>
        <Form.Fieldset>
          <Input
            label="URL (Optional)"
            placeholder="Enter a URL to the MCP server"
            {...register(`mcpServerSettings.${index}.url`)}
            error={getFieldError('url')}
            description="Enter a URL to the MCP server"
          />
        </Form.Fieldset>

        <Box mb="$16">
          <Box display="flex" justifyContent="space-between" alignItems="center" mb="$8">
            <Typography fontSize="$16" fontWeight={500} color="content.primary">
              Headers
            </Typography>
          </Box>
          <Typography fontSize="$12" color="content.subtle" mb="$16">
            Specified values will be added to the headers when making requests to the MCP Server.
          </Typography>

          <Form.Fieldset>
            {headerEntries.length > 0 && (
              <Box display="flex" flexDirection="column" gap="$16" width="100%" mb="$16">
                {headerEntries.map(([headerKey, headerValue]) => {
                  const displayKey = editingKeys[headerKey] !== undefined ? editingKeys[headerKey] : headerKey;

                  return (
                    <Box key={`header-${headerKey}`} display="flex" gap="$16" alignItems="flex-end" width="100%">
                      <Box style={{ flex: 1 }}>
                        <Input
                          label="Key"
                          value={displayKey}
                          onChange={(e) => handleKeyInputChange(headerKey, e.target.value)}
                          onBlur={() => handleKeyInputBlur(headerKey)}
                          placeholder="Header key"
                          width="100%"
                        />
                      </Box>
                      <Box style={{ flex: 1 }}>
                        <Select
                          label="Type"
                          value={headerValue.type === 'oauth2-secret' ? 'secret' : headerValue.type}
                          onChange={(value) => updateHeaderType(headerKey, value as 'string' | 'secret')}
                          width="100%"
                          items={typeOptions}
                        />
                      </Box>
                      <Box style={{ flex: 1 }}>
                        {headerValue.type === 'secret' || headerValue.type === 'oauth2-secret' ? (
                          <McpHeaderSecretInput
                            headerKey={headerKey}
                            headerValue={headerValue.value}
                            items={
                              secrets?.map((secret) => ({
                                value: secret.id,
                                label: secret.name,
                              })) || []
                            }
                            onUpdateValue={updateHeaderSecretValue}
                            onUpdateSecretId={updateHeaderSecretId}
                            onResetToValue={resetHeaderToValue}
                            disabled={isLoadingSecrets}
                          />
                        ) : (
                          <Input
                            label="Value"
                            value={headerValue.value.type === 'string' ? headerValue.value.value : ''}
                            onChange={(e) => updateHeaderValue(headerKey, e.target.value)}
                            type="text"
                            placeholder="Header value"
                            width="100%"
                          />
                        )}
                      </Box>
                      <Button
                        variant="secondary"
                        icon={IconTrash}
                        onClick={() => removeHeader(headerKey)}
                        aria-label="Remove header"
                      />
                    </Box>
                  );
                })}
              </Box>
            )}
            <Box display="flex" justifyContent="flex-start">
              <Button round variant="outline" icon={IconPlus} onClick={addNewHeader} size="small">
                Header
              </Button>
            </Box>
          </Form.Fieldset>
        </Box>
      </PackageCard>
    </Box>
  );
};
