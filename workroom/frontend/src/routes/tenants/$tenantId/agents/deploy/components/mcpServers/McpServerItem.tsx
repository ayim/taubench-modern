import { FC } from 'react';
import { Box, Input, Typography, Form, Button, Select } from '@sema4ai/components';
import { IconPlus, IconTrash } from '@sema4ai/icons';
import { useFormContext, useFieldArray } from 'react-hook-form';
import { PackageCard } from '@sema4ai/layouts';
import { AgentDeploymentFormSchema } from '../context';
import { mcpTypeSelectItems, mcpTransportSelectItems, headerTypeSelectItems } from '~/lib/mcpServersUtils';

type Props = {
  index: number;
  onRemove: () => void;
};

export const McpServerItem: FC<Props> = ({ index, onRemove }) => {
  const { register, watch, setValue, control } = useFormContext<AgentDeploymentFormSchema>();

  const serverSettings = watch(`mcpServerSettings.${index}`);

  const {
    fields: headerFields,
    append: appendHeader,
    remove: removeHeader,
  } = useFieldArray({
    control,
    name: `mcpServerSettings.${index}.headersKV`,
  });

  if (!serverSettings) {
    return null;
  }

  const readOnly = Boolean(serverSettings.mcpServerId);

  return (
    <Box p="$0" display="flex" flexDirection="column" gap="$16">
      <PackageCard
        title={
          <Box display="flex" alignItems="center" gap="$8" width="100%">
            <Typography>{serverSettings.name || 'New MCP Server'}</Typography>
            <Button variant="outline" size="small" icon={IconTrash} aria-label="Remove MCP server" onClick={onRemove}>
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
              value={serverSettings.type ?? 'generic_mcp'}
              items={[...mcpTypeSelectItems]}
              readOnly={readOnly}
              onChange={(value) => {
                if (value === 'generic_mcp' || value === 'sema4ai_action_server') {
                  setValue(`mcpServerSettings.${index}.type`, value);
                }
              }}
            />
            <Select
              label="Transport"
              value={serverSettings.transport ?? 'auto'}
              items={[...mcpTransportSelectItems]}
              readOnly={readOnly}
              onChange={(value) => {
                if (value === 'auto' || value === 'streamable-http' || value === 'sse' || value === 'stdio') {
                  setValue(`mcpServerSettings.${index}.transport`, value);
                }
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
            {headerFields.length > 0 && (
              <Box display="flex" flexDirection="column" gap="$16" width="100%">
                {headerFields.map((field, headerIndex) => {
                  const headerType = watch(`mcpServerSettings.${index}.headersKV.${headerIndex}.type`);

                  return (
                    <Box key={field.id} display="flex" gap="$16" alignItems="flex-end" width="100%">
                      <Box style={{ flex: 1 }}>
                        <Input
                          label="Key"
                          placeholder="Header key"
                          width="100%"
                          readOnly={readOnly}
                          {...register(`mcpServerSettings.${index}.headersKV.${headerIndex}.key`)}
                        />
                      </Box>
                      <Box style={{ flex: 1 }}>
                        <Select
                          label="Type"
                          value={headerType ?? 'string'}
                          onChange={(value) => {
                            if (value === 'string' || value === 'secret') {
                              setValue(`mcpServerSettings.${index}.headersKV.${headerIndex}.type`, value);
                            }
                          }}
                          width="100%"
                          items={[...headerTypeSelectItems]}
                          readOnly={readOnly}
                        />
                      </Box>
                      <Box style={{ flex: 1 }}>
                        <Input
                          label="Value"
                          type={headerType === 'secret' ? 'password' : 'text'}
                          placeholder={headerType === 'secret' ? 'Secret value' : 'Header value'}
                          width="100%"
                          readOnly={readOnly}
                          {...register(`mcpServerSettings.${index}.headersKV.${headerIndex}.value`)}
                        />
                      </Box>
                      <Button
                        variant="secondary"
                        icon={IconTrash}
                        onClick={() => removeHeader(headerIndex)}
                        aria-label="Remove header"
                        disabled={readOnly}
                      />
                    </Box>
                  );
                })}
              </Box>
            )}
            <Box display="flex" justifyContent="flex-start">
              <Button
                round
                variant="outline"
                icon={IconPlus}
                onClick={() => appendHeader({ key: '', value: '', type: 'string' })}
                size="small"
                disabled={readOnly}
              >
                Header
              </Button>
            </Box>
          </Form.Fieldset>
        </Box>
      </PackageCard>
    </Box>
  );
};
