import { Box, Button, Typography } from '@sema4ai/components';
import { IconCloseSmall, IconDbSchema, IconPencil } from '@sema4ai/icons';
import { FC } from 'react';

import { SchemaFormItem } from '../../form';

type Props = {
  schemas: SchemaFormItem[];
  onRemoveSchema: (index: number) => void;
  onEditSchema?: (index: number) => void;
};

export const SchemaList: FC<Props> = ({ schemas, onRemoveSchema, onEditSchema }) => {
  if (schemas.length === 0) {
    return null;
  }

  return (
    <Box py="$24">
      <Typography fontWeight="medium" mb="$8">
        Added schemas ({schemas.length})
      </Typography>
      <Box display="flex" flexDirection="column" gap="$8">
        {schemas.map((schema, index) => (
          <Box
            key={`${schema.name}`}
            display="flex"
            flexDirection="row"
            borderRadius="$8"
            borderWidth={1}
            borderColor="border.subtle"
            backgroundColor="background.panels"
            p="$8"
            onClick={onEditSchema ? () => onEditSchema(index) : undefined}
            as={onEditSchema ? 'button' : 'div'}
          >
            <Box flex="1" display="flex" alignItems="center" gap="$8" px="$8">
              <IconDbSchema />
              <Box>
                <Typography fontWeight="medium">{schema.name}</Typography>
                <Typography variant="body-small" color="content.subtle">
                  {schema.description}
                </Typography>
              </Box>
              <Box ml="auto" display="flex" gap="$4">
                {onEditSchema && (
                  <Button
                    aria-label="Edit schema"
                    variant="ghost-subtle"
                    size="small"
                    icon={IconPencil}
                    onClick={(e) => {
                      e.stopPropagation();
                      onEditSchema(index);
                    }}
                  />
                )}
                <Button
                  aria-label="Remove schema"
                  variant="ghost-subtle"
                  size="small"
                  icon={IconCloseSmall}
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemoveSchema(index);
                  }}
                />
              </Box>
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
};
