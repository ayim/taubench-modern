import { Box, Button, Code, Input, Tooltip, useClipboard, useSnackbar } from '@sema4ai/components';
import { IconCheck2, IconCopy, IconEye, IconEyeOff } from '@sema4ai/icons';
import { type FC, useCallback, useState } from 'react';
import { trpc } from '~/lib/trpc';
import { getPublicApiEndpointUrl } from '~/lib/utils';

// The length is currently matching the API key length
// Not "important", just nicer UX wise: the masking matches exactly the revealed API key
const MASKED_API_KEY = '•'.repeat(68);

type Props = {
  apiKey: {
    id: string;
    decryptedValue: string | null;
  };
  tenantId: string;
};

export const ApiKeyDisplay: FC<Props> = ({ apiKey, tenantId }) => {
  const endpointUrl = getPublicApiEndpointUrl({ origin: window.location.origin, tenantId });
  const { addSnackbar } = useSnackbar();
  const { onCopyToClipboard: onCopyApiKey, copiedToClipboard: apiKeyCopied } = useClipboard();
  const { onCopyToClipboard: onCopyEndpoint, copiedToClipboard: endpointCopied } = useClipboard();
  const [revealedValue, setRevealedValue] = useState<string | null>(null);
  const [isVisible, setIsVisible] = useState(apiKey.decryptedValue !== null);

  const previewMutation = trpc.apiKeys.preview.useMutation();

  const actualValue = apiKey.decryptedValue ?? revealedValue;
  const canReveal = apiKey.decryptedValue === null;

  const handleToggleVisibility = useCallback(() => {
    if (!actualValue && canReveal) {
      previewMutation.mutate(
        { id: apiKey.id },
        {
          onSuccess: (previewResult) => {
            setRevealedValue(previewResult.value);
            setIsVisible(true);
          },
          onError: (error) => addSnackbar({ message: error.message, variant: 'danger' }),
        },
      );
      return;
    }
    setIsVisible((previous) => !previous);
  }, [actualValue, canReveal, apiKey.id, previewMutation, addSnackbar]);

  const handleCopyApiKey = useCallback(() => {
    if (!actualValue) {
      return;
    }

    onCopyApiKey(actualValue)();
  }, [actualValue, onCopyApiKey]);

  const displayedValue = actualValue && isVisible ? actualValue : MASKED_API_KEY;

  const toolbar = (
    <Box display="flex" gap="$4" alignItems="center">
      {canReveal && (
        <Tooltip text={isVisible ? 'Hide' : 'Show'}>
          <Button
            aria-label={isVisible ? 'Hide API key' : 'Show API key'}
            variant="inverted"
            size="small"
            icon={isVisible ? IconEyeOff : IconEye}
            onClick={handleToggleVisibility}
            loading={previewMutation.isPending}
          >
            {isVisible ? 'Hide' : 'Show'}
          </Button>
        </Tooltip>
      )}
      {actualValue && (
        <Tooltip text="Copy to clipboard">
          <Button
            aria-label="Copy API key"
            variant="inverted"
            size="small"
            icon={apiKeyCopied ? IconCheck2 : IconCopy}
            onClick={handleCopyApiKey}
          />
        </Tooltip>
      )}
    </Box>
  );

  return (
    <Box display="flex" flexDirection="column" gap="$16">
      <Code
        aria-label="API Key"
        title="API Key"
        value={displayedValue}
        readOnly
        lineNumbers={false}
        theme="light"
        toolbar={toolbar}
      />
      <Box display="flex" flexDirection="column" gap="$8">
        <Box color="content.primary">This API key is only valid for the following URL:</Box>
        <Input
          aria-label="Endpoint URL"
          value={endpointUrl}
          readOnly
          iconRight={endpointCopied ? IconCheck2 : IconCopy}
          iconRightLabel="Copy to clipboard"
          onIconRightClick={onCopyEndpoint(endpointUrl)}
        />
      </Box>
    </Box>
  );
};
