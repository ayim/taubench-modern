import { FC, Suspense, useMemo } from 'react';
import { Box, Button, Tooltip, useClipboard } from '@sema4ai/components';
import { IconCheck2, IconCopy } from '@sema4ai/icons';

import { CodeProps, Code as CodeBase } from './Code';

export const Code: FC<CodeProps> = ({ value, toolbar: customToolbar, ...restProps }) => {
  const { onCopyToClipboard, copiedToClipboard } = useClipboard();

  const toolbar = useMemo(() => {
    return (
      <Box display="flex" gap="$6" justifyContent="center" minWidth={40}>
        {customToolbar}
        <Tooltip text="Copy to clipboard">
          <Button
            aria-label="Copy to clipboard"
            variant="inverted"
            round
            icon={copiedToClipboard ? IconCheck2 : IconCopy}
            onClick={onCopyToClipboard(value)}
            size="small"
          />
        </Tooltip>
      </Box>
    );
  }, [value, customToolbar, copiedToClipboard]);

  return (
    <Suspense fallback="">
      <CodeBase toolbar={toolbar} value={value} {...restProps} />
    </Suspense>
  );
};
