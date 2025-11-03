import { Input, useClipboard } from '@sema4ai/components';
import { IconCheck2, IconCopy } from '@sema4ai/icons';
import { useWorkItemAPIUrlQuery } from '../../queries/workItemAPI';

export const WorkItemAPIUrl = () => {
  const { onCopyToClipboard, copiedToClipboard } = useClipboard();
  const { data: workItemApiUrl } = useWorkItemAPIUrlQuery({});

  if (!workItemApiUrl) {
    return null;
  }

  return (
    <Input
      value={workItemApiUrl}
      readOnly
      iconRight={copiedToClipboard ? IconCheck2 : IconCopy}
      onIconRightClick={onCopyToClipboard(workItemApiUrl)}
      iconRightLabel="Copy URL"
      aria-label="workItem-api-url"
    />
  );
};
