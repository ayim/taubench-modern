import { useParams } from '@tanstack/react-router';
import { Button, Menu, Tooltip, useScreenSize } from '@sema4ai/components';
import { ThreadHeader } from '@sema4ai/spar-ui';
import { useAgentQuery } from '@sema4ai/spar-ui/queries';
import {
  IconChemicalBottle,
  IconDotsHorizontal,
  IconDoubleChatBubble,
  IconPaperclip,
  IconSpreadsheet,
} from '@sema4ai/icons';

import { RouterMenuLink, RouterSideNavigationLink } from '~/components/RouterLink';
import { NEW_CHAT_STARTING_MSG } from '~/config/constants';
import { useTenantContext } from '~/lib/tenantContext';

export const Header = () => {
  const { agentId, tenantId, threadId } = useParams({ from: '/tenants/$tenantId/conversational/$agentId/$threadId' });
  const isMobile = useScreenSize('m');
  const { features } = useTenantContext();

  const { data: agent, isLoading } = useAgentQuery({ agentId });

  if (isLoading || !agent) {
    return null;
  }

  return (
    <ThreadHeader newThreadStartingMesssage={NEW_CHAT_STARTING_MSG}>
      {!isMobile && (
        <>
          <Tooltip text="Chat" placement="bottom">
            <RouterSideNavigationLink
              to="/tenants/$tenantId/conversational/$agentId/$threadId"
              icon={<IconDoubleChatBubble />}
              round
              params={{ tenantId, agentId, threadId }}
              activeOptions={{ exact: true }}
            />
          </Tooltip>

          <Tooltip text="Files" placement="bottom">
            <RouterSideNavigationLink
              to="/tenants/$tenantId/conversational/$agentId/$threadId/files"
              icon={<IconPaperclip />}
              round
              params={{ tenantId, agentId, threadId }}
            />
          </Tooltip>

          <Tooltip text="Data Frames" placement="bottom">
            <RouterSideNavigationLink
              to="/tenants/$tenantId/conversational/$agentId/$threadId/data-frames"
              icon={<IconSpreadsheet />}
              round
              params={{ tenantId, agentId, threadId }}
            />
          </Tooltip>

          {features.agentEvals.enabled && (
            <Tooltip text="Evaluations" placement="bottom">
              <RouterSideNavigationLink
                to="/tenants/$tenantId/conversational/$agentId/$threadId/evaluations"
                icon={IconChemicalBottle}
                round
                params={{ tenantId, agentId, threadId }}
              />
            </Tooltip>
          )}
        </>
      )}
      {isMobile && (
        <>
          <Menu trigger={<Button icon={IconDotsHorizontal} variant="ghost" aria-label="Chat Actions" />}>
            <RouterMenuLink
              to="/tenants/$tenantId/conversational/$agentId/$threadId"
              icon={IconDoubleChatBubble}
              params={{ tenantId, agentId, threadId }}
            >
              Chat
            </RouterMenuLink>
            <RouterMenuLink
              to="/tenants/$tenantId/conversational/$agentId/$threadId/files"
              icon={IconPaperclip}
              params={{ tenantId, agentId, threadId }}
            >
              Files
            </RouterMenuLink>
            <RouterMenuLink
              to="/tenants/$tenantId/conversational/$agentId/$threadId/data-frames"
              icon={IconSpreadsheet}
              params={{ tenantId, agentId, threadId }}
            >
              Data Frames
            </RouterMenuLink>
            {features.agentEvals.enabled && (
              <RouterMenuLink
                to="/tenants/$tenantId/conversational/$agentId/$threadId/evaluations"
                icon={IconChemicalBottle}
                params={{ tenantId, agentId, threadId }}
              >
                Evaluations
              </RouterMenuLink>
            )}
          </Menu>
        </>
      )}
    </ThreadHeader>
  );
};
