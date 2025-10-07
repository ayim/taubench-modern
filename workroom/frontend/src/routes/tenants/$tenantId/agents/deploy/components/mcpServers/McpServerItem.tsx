import { FC, useState } from 'react';
import { Box, Input, Typography, Form, Button, Select } from '@sema4ai/components';
import { IconPlus, IconTrash } from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';
import { PackageCard } from '@sema4ai/layouts';
import { InputControlled } from '~/components/InputControlled';
import { AgentDeploymentFormSchema, MCPServerSettings, MCPHeaderValue } from '../context';

type Props = {
  index: number;
  mcpServer: MCPServerSettings;
};

export const McpServerItem: FC<Props> = ({ index, mcpServer }) => {
  const { register, watch, getValues, setValue, trigger } = useFormContext<AgentDeploymentFormSchema>();

  const mcpServerSettings = watch(`mcpServerSettings.${index}`);
  const [editingKeys, setEditingKeys] = useState<Record<string, string>>({});

  const headers = mcpServerSettings?.headers ?? {};
  const headerEntries = Object.entries(headers);

  const typeOptions = [
    { label: 'Plain Text', value: 'string' },
    { label: 'Secret', value: 'secret' },
  ];

  const updateMcpServerSettings = async (updater: (settings: MCPServerSettings) => MCPServerSettings) => {
    const currentSettings = getValues('mcpServerSettings') || [];
    const updatedSettings = [...currentSettings];
    if (updatedSettings[index]) {
      updatedSettings[index] = updater(updatedSettings[index]);
      setValue('mcpServerSettings', updatedSettings, { shouldValidate: true, shouldDirty: true });
      await trigger(`mcpServerSettings.${index}`);
    }
  };

  const createHeaderValue = (type: 'string' | 'secret', currentHeader?: MCPHeaderValue, value = ''): MCPHeaderValue => {
    if (type === 'secret') {
      return {
        type: 'secret',
        value,
        description: currentHeader?.description,
      };
    }

    return {
      type: 'string',
      value,
      description: currentHeader?.description,
    };
  };

  const addNewHeader = () => {
    const tempKey = `new_header_${Date.now()}`;
    updateMcpServerSettings((settings) => ({
      ...settings,
      headers: {
        ...(settings.headers ?? {}),
        [tempKey]: createHeaderValue('string'),
      },
    }));
  };

  const removeHeader = (key: string) =>
    updateMcpServerSettings((settings) => ({
      ...settings,
      headers: Object.fromEntries(Object.entries(settings.headers ?? {}).filter(([k]) => k !== key)),
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

  const updateHeaderType = (key: string, type: 'string' | 'secret') =>
    updateMcpServerSettings((settings) => {
      const currentHeader = settings.headers?.[key];
      if (!currentHeader) return settings;

      return {
        ...settings,
        headers: {
          ...(settings.headers ?? {}),
          [key]: createHeaderValue(type, currentHeader, currentHeader.value ?? ''),
        },
      };
    });

  const handleKeyInputChange = (originalKey: string, newValue: string) => {
    setEditingKeys((prev) => ({ ...prev, [originalKey]: newValue }));
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

  const readOnly = Boolean(mcpServer.mcpServerId);

  return (
    <Box p="$0" display="flex" flexDirection="column" gap="$16">
      <PackageCard
        title={
          <Box display="flex" alignItems="center" gap="$8" width="100%">
            <Typography>{mcpServerSettings?.name}</Typography>
            <Button
              variant="outline"
              size="small"
              icon={IconTrash}
              aria-label="Remove MCP server"
              onClick={async () => {
                const current = getValues('mcpServerSettings') || [];
                const removed = current[index];
                const next = current.filter((_, i) => i !== index);
                setValue('mcpServerSettings', next, { shouldDirty: true, shouldValidate: true });
                if (removed?.mcpServerId) {
                  const remainingIds = (getValues('mcpServerIds') || []).filter(
                    (x: string) => x !== removed.mcpServerId,
                  );
                  setValue('mcpServerIds', remainingIds, { shouldDirty: true, shouldValidate: true });
                }
                await trigger('mcpServerSettings');
              }}
            >
              Remove
            </Button>
          </Box>
        }
        description={readOnly ? 'Global configured MCP server' : null}
        version={null}
      >
        <Form.Fieldset>
          <Input
            label="MCP Server Name"
            placeholder="Enter a name for this MCP server"
            {...register(`mcpServerSettings.${index}.name`)}
            description="A descriptive name for this MCP server"
            readOnly={readOnly}
          />
          <Box display="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <Select
              label="Type"
              value={mcpServerSettings?.type ?? 'generic_mcp'}
              items={[
                { label: 'Generic MCP', value: 'generic_mcp' },
                { label: 'Sema4 Action Server', value: 'sema4ai_action_server' },
              ]}
              readOnly={readOnly}
              onChange={async (value) => {
                if (value !== 'generic_mcp' && value !== 'sema4ai_action_server') return;
                await updateMcpServerSettings((settings) => ({
                  ...settings,
                  type: value,
                }));
              }}
            />
          </Box>
          <Input
            label="URL (Optional)"
            placeholder="Enter a URL to the MCP server"
            {...register(`mcpServerSettings.${index}.url`)}
            description="Enter a URL to the MCP server"
            readOnly={readOnly}
          />
        </Form.Fieldset>

        <Box>
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
              <Box display="flex" flexDirection="column" gap="$16" width="100%">
                {headerEntries.map(([headerKey, headerValue]) => {
                  const displayKey = editingKeys[headerKey] !== undefined ? editingKeys[headerKey] : headerKey;

                  if (!headerValue) return null;

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
                          readOnly={readOnly}
                        />
                      </Box>
                      <Box style={{ flex: 1 }}>
                        <Select
                          label="Type"
                          value={headerValue.type}
                          onChange={(value) => {
                            if (value === 'string' || value === 'secret') {
                              updateHeaderType(headerKey, value);
                            }
                          }}
                          width="100%"
                          items={typeOptions}
                          readOnly={readOnly}
                        />
                      </Box>
                      <Box style={{ flex: 1 }}>
                        <InputControlled
                          fieldName={`mcpServerSettings.${index}.headers.${headerKey}.value`}
                          label="Value"
                          type={headerValue.type === 'secret' ? 'password' : 'text'}
                          placeholder={headerValue.type === 'secret' ? `Secret for ${headerKey}` : 'Header value'}
                          width="100%"
                          readOnly={readOnly}
                        />
                      </Box>
                      <Button
                        variant="secondary"
                        icon={IconTrash}
                        onClick={() => removeHeader(headerKey)}
                        aria-label="Remove header"
                        disabled={readOnly}
                      />
                    </Box>
                  );
                })}
              </Box>
            )}
            <Box display="flex" justifyContent="flex-start">
              <Button round variant="outline" icon={IconPlus} onClick={addNewHeader} size="small" disabled={readOnly}>
                Header
              </Button>
            </Box>
          </Form.Fieldset>
        </Box>
      </PackageCard>
    </Box>
  );
};
