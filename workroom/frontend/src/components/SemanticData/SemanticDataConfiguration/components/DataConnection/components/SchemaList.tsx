import { Box, Button, Typography } from '@sema4ai/components';
import { IconCloseSmall, IconDbSchema } from '@sema4ai/icons';
import { FC } from 'react';

import { SchemaFormItem } from '../../form';

type Props = {
  schemas: SchemaFormItem[];
  onRemoveSchema: (index: number) => void;
};

export const SchemaList: FC<Props> = ({ schemas, onRemoveSchema }) => {
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
            borderRadius={8}
            borderWidth={1}
            borderColor="border.subtle"
            backgroundColor="background.panels"
            p={8}
          >
            <Box flex="1" display="flex" alignItems="center" gap="$8" px="$8">
              <IconDbSchema />
              <Box>
                <Typography fontWeight="medium">{schema.name}</Typography>
                <Typography variant="body-small" color="content.subtle">
                  {schema.description}
                </Typography>
              </Box>
              <Box ml="auto">
                <Button
                  aria-label="Remove schema"
                  variant="ghost-subtle"
                  size="small"
                  icon={IconCloseSmall}
                  onClick={() => onRemoveSchema(index)}
                />
              </Box>
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
};
