import { Input, useClipboard } from '@sema4ai/components';
import { IconCheck2, IconCopy } from '@sema4ai/icons';
import { useParams } from '@tanstack/react-router';

import { useAgentDetailsContext } from './context';

export const Endpoints = () => {
  const { tenantId } = useParams({ strict: false });
  const { onCopyToClipboard: onCopyMCP, copiedToClipboard: mcpCopied } = useClipboard();
  const { onCopyToClipboard: onCopyWorkItems, copiedToClipboard: workItemsCopied } = useClipboard();
  const { onCopyToClipboard: onCopyAgentAPI, copiedToClipboard: agentAPICopied } = useClipboard();
  const { agent } = useAgentDetailsContext();

  const mcpEndpoint = `${window.location.origin}/tenants/${tenantId}/api/v1/agent-mcp/${agent.id}/mcp/`;
  const workItemsEndpoint = `${window.location.origin}/tenants/${tenantId}/api/v1/work-items/`;
  const agentAPIEndpoint = `${window.location.origin}/tenants/${tenantId}/api/v1/agents/${agent.id}`;

  return (
    <>
      <Input
        label="Agent MCP Server Endpoint"
        readOnly
        value={mcpEndpoint}
        iconRight={mcpCopied ? IconCheck2 : IconCopy}
        iconRightLabel="Copy to clipboard"
        onIconRightClick={onCopyMCP(mcpEndpoint)}
      />
      {agent.mode === 'worker' && (
        <Input
          label="Work items API endpoint"
          readOnly
          value={workItemsEndpoint}
          iconRight={workItemsCopied ? IconCheck2 : IconCopy}
          iconRightLabel="Copy to clipboard"
          onIconRightClick={onCopyWorkItems(workItemsEndpoint)}
        />
      )}
      {agent.mode === 'conversational' && (
        <Input
          label="Agent API endpoint"
          readOnly
          value={agentAPIEndpoint}
          iconRight={agentAPICopied ? IconCheck2 : IconCopy}
          iconRightLabel="Copy to clipboard"
          onIconRightClick={onCopyAgentAPI(agentAPIEndpoint)}
        />
      )}
    </>
  );
};
