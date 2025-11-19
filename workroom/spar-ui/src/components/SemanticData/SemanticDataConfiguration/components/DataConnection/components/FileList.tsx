import { Box, Button, Typography } from '@sema4ai/components';
import { IconCloseSmall, IconDbSpreadsheet } from '@sema4ai/icons';
import { FC } from 'react';

type Props = {
  files: string[];
  onRemoveFile: (file: string) => void;
};

export const FileList: FC<Props> = ({ files, onRemoveFile }) => {
  if (files.length === 0) {
    return null;
  }

  return (
    <Box py="$24">
      <Typography fontWeight="medium" mb="$8">
        Added files
      </Typography>
      <Box
        display="flex"
        flexDirection="row"
        borderRadius={8}
        borderWidth={1}
        borderColor="border.subtle"
        backgroundColor="background.panels"
        p={8}
      >
        {files.map((file) => (
          <Box flex="1" key={file} display="flex" alignItems="center" gap="$8" px="$8">
            <IconDbSpreadsheet />
            <Typography>{file}</Typography>
            <Box ml="auto">
              <Button
                aria-label="Remove file"
                variant="ghost-subtle"
                size="small"
                icon={IconCloseSmall}
                onClick={() => onRemoveFile(file)}
              />
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
};
