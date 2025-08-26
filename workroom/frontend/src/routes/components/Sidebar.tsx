import { Circle, cn } from '@sema4ai/agent-components';
import { Box, Scroll, SideNavigation, Typography, usePopover } from '@sema4ai/components';
import {
  IconAgents,
  IconConversationalAgents,
  IconDocumentIntelligence,
  IconHelpCircle,
  IconHome,
  IconSettings2,
  IconUnorderedList,
  IconWorkers,
} from '@sema4ai/icons';
import { Link as LinkBase, useMatch, useParams } from '@tanstack/react-router';
import { FC, memo, ReactNode, useEffect, useMemo, useState } from 'react';
import { useMeta } from '~/hooks/meta';
import { useTenantContext } from '~/lib/tenantContext';
import { Agent } from '~/types';
import { isConversationalAgent, isWorkerAgent } from '~/utils';
import { ACE_WORKROOM_VERSION } from '~/version';

type SideBarProps = {
  agents: Agent[];
};

const linkActiveProp = {
  className: cn('[&>*]:!bg-[rgba(var(--color-background-subtle))]', '[&_*]:!text-[rgba(var(--color-content-primary))]'),
};

// Removed custom Link wrapper to preserve TanStack Router generics for params

const CustomDivider: FC = memo(() => {
  return (
    <div className="last:hidden">
      <hr className="bg-[#D9D9D9] h-[1px] mx-4" />
    </div>
  );
});

const AgentEntryLink: FC<{ agent: Agent }> = memo(({ agent }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  // TODO: v2 integration, remove this nullish coalescing in agent.id 2 places
  return (
    <LinkBase
      to="/tenants/$tenantId/$agentId"
      params={{ tenantId, agentId: agent.id ?? '' }}
      className={cn('w-full hover:[&>*]:!bg-[rgba(var(--color-background-subtle))]')}
      activeProps={linkActiveProp}
    >
      <SideNavigation.Item
        icon={<Circle identifier={agent.id ?? ''} />}
        className={cn('group-[:not(:hover)]/sidebar:!pl-[10px] !transition-[padding-left] ')}
        as="div"
      >
        {agent.name}
      </SideNavigation.Item>
    </LinkBase>
  );
});

const AgentsAccordion: FC<{
  initiallyOpen?: boolean;
  name: string;
  icon: ReactNode;
  agents: Agent[];
}> = memo(({ initiallyOpen, name, icon, agents }) => {
  const [isOpen, setIsOpen] = useState<boolean>(!!initiallyOpen);

  return (
    <SideNavigation.Accordion
      title={name}
      icon={icon}
      open={isOpen}
      onClick={() => setIsOpen((currentIsOpen) => !currentIsOpen)}
      className={cn(
        'group-[:not(:hover)]/sidebar:[&>div:last-child]:hidden',
        '[&+div]:!pl-3 group-[:not(:hover)]/sidebar:[&+div]:!pl-0 [&+div]:transition-[padding-left]',
        'hover:!bg-gray-200',
      )}
    >
      {agents.map((agent) => (
        <AgentEntryLink agent={agent} key={agent.id} />
      ))}
    </SideNavigation.Accordion>
  );
});

const MyAgentsItems: FC<{ agents: Agent[] }> = memo(({ agents }) => {
  const conversationalAgents = useMemo(() => agents.filter((agent) => isConversationalAgent(agent)), [agents]);
  const workerAgents = useMemo(() => agents.filter((agent) => isWorkerAgent(agent)), [agents]);

  return (
    <Scroll className="px-2 overflow-hidden group-[:not(:hover)]/sidebar:[&>*]:hide-scrollbar" tabIndex={-1}>
      {conversationalAgents.length > 0 && (
        <AgentsAccordion
          name="Conversational Agents"
          icon={<IconConversationalAgents size={21} />}
          agents={conversationalAgents}
          initiallyOpen
        />
      )}
      {workerAgents.length > 0 && (
        <AgentsAccordion name="Worker Agents" icon={<IconWorkers size={21} />} agents={workerAgents} initiallyOpen />
      )}
    </Scroll>
  );
});

const HomeLink: FC = memo(() => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  return (
    <SideNavigation.ItemGroup>
      <LinkBase
        to="/tenants/$tenantId/home"
        params={{ tenantId }}
        className={cn('w-full hover:[&>*]:!bg-[rgba(var(--color-background-subtle))]')}
        activeProps={linkActiveProp}
      >
        <SideNavigation.Item icon={<IconHome />}>Home</SideNavigation.Item>
      </LinkBase>
    </SideNavigation.ItemGroup>
  );
});

const AgentsLink: FC = memo(() => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  return (
    <SideNavigation.ItemGroup>
      <LinkBase
        to="/tenants/$tenantId/agents"
        params={{ tenantId }}
        className={cn('w-full hover:[&>*]:!bg-[rgba(var(--color-background-subtle))]')}
        activeProps={linkActiveProp}
      >
        <SideNavigation.Item icon={<IconAgents />}>Agents</SideNavigation.Item>
      </LinkBase>
    </SideNavigation.ItemGroup>
  );
});

const DocumentsLink: FC = memo(() => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  return (
    <SideNavigation.ItemGroup>
      <LinkBase
        to="/tenants/$tenantId/documentIntelligence"
        params={{ tenantId }}
        className={cn('w-full hover:[&>*]:!bg-[rgba(var(--color-background-subtle))]')}
        activeProps={linkActiveProp}
      >
        <SideNavigation.Item icon={<IconDocumentIntelligence />}>Document Intelligence</SideNavigation.Item>
      </LinkBase>
    </SideNavigation.ItemGroup>
  );
});

const AgentDeploymentLink: FC = memo(() => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  return (
    <SideNavigation.ItemGroup>
      <LinkBase
        to="/tenants/$tenantId/agents/create"
        params={{ tenantId }}
        className={cn('w-full hover:[&>*]:!bg-[rgba(var(--color-background-subtle))]')}
        activeProps={linkActiveProp}
      >
        <SideNavigation.Item icon={<IconAgents />}>Create Agent</SideNavigation.Item>
      </LinkBase>
    </SideNavigation.ItemGroup>
  );
});

const WorkItemsLink: FC = memo(() => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  return (
    <SideNavigation.ItemGroup>
      <LinkBase
        to="/tenants/$tenantId/workItems"
        params={{ tenantId }}
        className={cn('w-full hover:[&>*]:!bg-[rgba(var(--color-background-subtle))]')}
        activeProps={linkActiveProp}
      >
        <SideNavigation.Item icon={<IconUnorderedList />}>Work Items</SideNavigation.Item>
      </LinkBase>
    </SideNavigation.ItemGroup>
  );
});

const SettingsLink: FC = memo(() => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  return (
    <SideNavigation.ItemGroup>
      <LinkBase
        to="/tenants/$tenantId/settings"
        params={{ tenantId }}
        className={cn('w-full hover:[&>*]:!bg-[rgba(var(--color-background-subtle))]')}
        activeProps={linkActiveProp}
      >
        <SideNavigation.Item icon={<IconSettings2 />}>Settings</SideNavigation.Item>
      </LinkBase>
    </SideNavigation.ItemGroup>
  );
});

const McpServersLink: FC = memo(() => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  return (
    <SideNavigation.ItemGroup>
      <LinkBase
        to={'/tenants/$tenantId/mcp-servers' as unknown as never}
        params={{ tenantId } as unknown as never}
        className={cn('w-full hover:[&>*]:!bg-[rgba(var(--color-background-subtle))]')}
        activeProps={linkActiveProp}
      >
        <SideNavigation.Item icon={<IconSettings2 />}>MCP servers</SideNavigation.Item>
      </LinkBase>
    </SideNavigation.ItemGroup>
  );
});

const HelpLink: FC = memo(() => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  return (
    <SideNavigation.ItemGroup>
      <LinkBase
        to="/tenants/$tenantId/help"
        params={{ tenantId }}
        className={cn('w-full hover:[&>*]:!bg-[rgba(var(--color-background-subtle))]')}
        activeProps={linkActiveProp}
      >
        <SideNavigation.Item icon={<IconHelpCircle />}>Help</SideNavigation.Item>
      </LinkBase>
    </SideNavigation.ItemGroup>
  );
});

const PoweredByStamp: FC = memo(() => {
  const { branding } = useTenantContext();
  const { setOpen, referenceRef, referenceProps, PopoverContent } = usePopover();
  const [aceId, setAceId] = useState<string | null>(null);
  const meta = useMeta();

  useEffect(() => {
    if (meta && 'aceId' in meta) {
      setAceId(meta.aceId);
    }
  }, [meta]);

  if (branding) {
    return null;
  }

  return (
    <SideNavigation.ItemGroup
      className={cn('overflow-hidden', '!h-0 !min-h-10 group-[:not(:hover)]/sidebar:!min-h-0 transition-[min-height]')}
      tabIndex={-1}
      disabled
    >
      <SideNavigation.Item tabIndex={-1} ref={referenceRef} {...referenceProps} onMouseEnter={() => setOpen(true)}>
        Powered by Sema4.ai
      </SideNavigation.Item>
      <PopoverContent>
        <Box
          p="$16"
          borderRadius="$8"
          color="content.inverted"
          backgroundColor="background.inverted"
          onClick={(e) => e.stopPropagation()}
          onMouseLeave={() => setOpen(false)}
        >
          {aceId && (
            <>
              <Typography fontWeight="bold" as="span">
                Agent Compute ID:{' '}
              </Typography>
              {aceId}
              <br />
            </>
          )}
          <Typography fontWeight="bold" as="span">
            Work Room build:
          </Typography>{' '}
          {ACE_WORKROOM_VERSION}
        </Box>
      </PopoverContent>
    </SideNavigation.ItemGroup>
  );
});

/**
 * TODO : Remove below when pages (Agents, Settings, Help) are ready
 */
const SHOW_PLACEHOLDER_PAGES = false;

export const Sidebar: FC<SideBarProps> = memo(({ agents }) => {
  const [open, setOpen] = useState<boolean>(false);
  // checking if "/$tenantId/$agentId" is matched
  const isAgentRouteMatched = !!useMatch({
    from: '/tenants/$tenantId/$agentId',
    shouldThrow: false,
  });

  const { features } = useTenantContext();

  return (
    <Box
      as={SideNavigation}
      aria-label="Left Navigation"
      open={open}
      onClose={() => setOpen(false)}
      className={cn(
        '!p-0 !pt-2 !overflow-hidden',
        isAgentRouteMatched && '[&:not(:hover)]:!w-[3.75rem] transition-[width] group/sidebar duration-300',
      )}
      backgroundColor="background.subtle.light"
      borderColor="grey80"
      borderWidth="0 1px 0 0"
    >
      <HomeLink />

      <AgentsLink />
      {features.documentIntelligence.enabled && <DocumentsLink />}
      <WorkItemsLink />
      {features.settings.enabled && <SettingsLink />}
      {features.mcpServersManagement.enabled && <McpServersLink />}
      {features.deploymentWizard.enabled && <AgentDeploymentLink />}
      {agents.length > 0 && (
        <>
          <CustomDivider />
          <MyAgentsItems agents={agents} />
        </>
      )}

      <Box mt="auto" />
      {SHOW_PLACEHOLDER_PAGES && <SettingsLink />}
      {SHOW_PLACEHOLDER_PAGES && <HelpLink />}
      <CustomDivider />
      <PoweredByStamp />
    </Box>
  );
});
