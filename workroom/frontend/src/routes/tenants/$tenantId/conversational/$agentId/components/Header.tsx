import { useParams } from '@tanstack/react-router';
import { Button, Menu, Tooltip, useScreenSize } from '@sema4ai/components';
import { ThreadHeader } from '@sema4ai/spar-ui';
import { useAgentQuery } from '@sema4ai/spar-ui/queries';
import {
  IconChemicalBottle,
  IconDotsHorizontal,
  IconMap,
  IconInformation,
  IconPaperclip,
  IconSpreadsheet,
} from '@sema4ai/icons';

import { RouterMenuLink, RouterSideNavigationLink } from '~/components/RouterLink';
import { useTenantContext } from '~/lib/tenantContext';
import { useToggleRoutePath } from '~/hooks/useToggleRoutePath';

export const Header = () => {
  const { agentId, tenantId, threadId } = useParams({ from: '/tenants/$tenantId/conversational/$agentId/$threadId' });
  const isMobile = useScreenSize('m');
  const { features } = useTenantContext();
  const defaultLink = {
    to: '/tenants/$tenantId/conversational/$agentId/$threadId',
    params: { tenantId, agentId, threadId },
  };

  const resolveLink = useToggleRoutePath(defaultLink);

  const { data: agent, isLoading } = useAgentQuery({ agentId });

  if (isLoading || !agent) {
    return null;
  }

  return (
    <ThreadHeader>
      {!isMobile && (
        <>
          <Tooltip text="Files" placement="bottom">
            <RouterSideNavigationLink
              {...resolveLink('/tenants/$tenantId/conversational/$agentId/$threadId/files', {
                tenantId,
                agentId,
                threadId,
              })}
              icon={<IconPaperclip />}
              round
            />
          </Tooltip>
          <Tooltip text="Details" placement="bottom">
            <RouterSideNavigationLink
              icon={<IconInformation />}
              round
              {...resolveLink('/tenants/$tenantId/conversational/$agentId/$threadId/chat-details', {
                tenantId,
                agentId,
                threadId,
              })}
            />
          </Tooltip>

          <Tooltip text="Data Frames" placement="bottom">
            <RouterSideNavigationLink
              icon={<IconSpreadsheet />}
              round
              {...resolveLink('/tenants/$tenantId/conversational/$agentId/$threadId/data-frames', {
                tenantId,
                agentId,
                threadId,
              })}
            />
          </Tooltip>

          {agent.question_groups && agent.question_groups.length > 0 && (
            <Tooltip text="Conversation Guides" placement="bottom">
              <RouterSideNavigationLink
                icon={<IconMap />}
                round
                {...resolveLink('/tenants/$tenantId/conversational/$agentId/$threadId/conversation-guides', {
                  tenantId,
                  agentId,
                  threadId,
                })}
              />
            </Tooltip>
          )}

          {features.agentEvals.enabled && (
            <Tooltip text="Evaluations" placement="bottom">
              <RouterSideNavigationLink
                icon={IconChemicalBottle}
                round
                {...resolveLink('/tenants/$tenantId/conversational/$agentId/$threadId/evaluations', {
                  tenantId,
                  agentId,
                  threadId,
                })}
              />
            </Tooltip>
          )}
        </>
      )}
      {isMobile && (
        <>
          <Menu trigger={<Button icon={IconDotsHorizontal} variant="ghost" aria-label="Chat Actions" />}>
            <RouterMenuLink
              icon={IconPaperclip}
              {...resolveLink('/tenants/$tenantId/conversational/$agentId/$threadId/files', {
                tenantId,
                agentId,
                threadId,
              })}
              params={{ tenantId, agentId, threadId }}
            >
              Files
            </RouterMenuLink>
            <RouterMenuLink
              icon={IconPaperclip}
              {...resolveLink('/tenants/$tenantId/conversational/$agentId/$threadId/chat-details', {
                tenantId,
                agentId,
                threadId,
              })}
              params={{ tenantId, agentId, threadId }}
            >
              Chat Details
            </RouterMenuLink>

            <RouterMenuLink
              icon={IconSpreadsheet}
              {...resolveLink('/tenants/$tenantId/conversational/$agentId/$threadId/data-frames', {
                tenantId,
                agentId,
                threadId,
              })}
              params={{ tenantId, agentId, threadId }}
            >
              Data Frames
            </RouterMenuLink>
            {features.agentEvals.enabled && (
              <RouterMenuLink
                icon={IconChemicalBottle}
                {...resolveLink('/tenants/$tenantId/conversational/$agentId/$threadId/evaluations', {
                  tenantId,
                  agentId,
                  threadId,
                })}
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
