import { Circle, cn } from '@sema4ai/agent-components';
import { Box, Scroll, SideNavigation, Typography, usePopover } from '@sema4ai/components';
import {
  IconAgents,
  IconConversationalAgents,
  IconDocumentIntelligence,
  IconHelpCircle,
  IconHome,
  IconSettings2,
  IconWorkers,
} from '@sema4ai/icons';
import { Link as LinkBase, LinkComponentProps, useMatch, useParams } from '@tanstack/react-router';
import { FC, memo, ReactNode, useEffect, useMemo, useState } from 'react';
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

const Link: FC<LinkComponentProps> = ({ className, ...rest }) => {
  return (
    <LinkBase
      className={cn('w-full hover:[&>*]:!bg-[rgba(var(--color-background-subtle))]', className)}
      activeProps={linkActiveProp}
      {...rest}
    />
  );
};

const CustomDivider: FC = memo(() => {
  return (
    <div className="last:hidden">
      <hr className="bg-[#D9D9D9] h-[1px] mx-4" />
    </div>
  );
});

const AgentEntryLink: FC<{ agent: Agent }> = memo(({ agent }) => {
  const { tenantId } = useParams({ from: '/$tenantId' });

  // TODO: v2 integration, remove this nullish coalescing in agent.id 2 places
  return (
    <Link to="/$tenantId/$agentId" params={{ tenantId, agentId: agent.id ?? '' }}>
      <SideNavigation.Item
        icon={<Circle identifier={agent.id ?? ''} />}
        className={cn('group-[:not(:hover)]/sidebar:!pl-[10px] !transition-[padding-left] ')}
        as="div"
      >
        {agent.name}
      </SideNavigation.Item>
    </Link>
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
  const { tenantId } = useParams({ from: '/$tenantId' });

  return (
    <SideNavigation.ItemGroup>
      <Link to="/$tenantId/home" params={{ tenantId }}>
        <SideNavigation.Item icon={<IconHome />}>Home</SideNavigation.Item>
      </Link>
    </SideNavigation.ItemGroup>
  );
});

const AgentsLink: FC = memo(() => {
  const { tenantId } = useParams({ from: '/$tenantId' });

  return (
    <SideNavigation.ItemGroup>
      <Link to="/$tenantId/agents" params={{ tenantId }}>
        <SideNavigation.Item icon={<IconAgents />}>Agents</SideNavigation.Item>
      </Link>
    </SideNavigation.ItemGroup>
  );
});

const DocumentsLink: FC = memo(() => {
  const { tenantId } = useParams({ from: '/$tenantId' });

  return (
    <SideNavigation.ItemGroup>
      <Link to="/$tenantId/documents" params={{ tenantId }}>
        <SideNavigation.Item icon={<IconDocumentIntelligence />}>Documents</SideNavigation.Item>
      </Link>
    </SideNavigation.ItemGroup>
  );
});

const SettingsLink: FC = memo(() => {
  const { tenantId } = useParams({ from: '/$tenantId' });

  return (
    <SideNavigation.ItemGroup>
      <Link to="/$tenantId/settings" params={{ tenantId }}>
        <SideNavigation.Item icon={<IconSettings2 />}>Settings</SideNavigation.Item>
      </Link>
    </SideNavigation.ItemGroup>
  );
});

const HelpLink: FC = memo(() => {
  const { tenantId } = useParams({ from: '/$tenantId' });

  return (
    <SideNavigation.ItemGroup>
      <Link to="/$tenantId/help" params={{ tenantId }}>
        <SideNavigation.Item icon={<IconHelpCircle />}>Help</SideNavigation.Item>
      </Link>
    </SideNavigation.ItemGroup>
  );
});

const PoweredByStamp: FC = memo(() => {
  const { branding } = useTenantContext();
  const { setOpen, referenceRef, referenceProps, PopoverContent } = usePopover();
  const [aceId, setAceId] = useState('-');

  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const response = await fetch('/meta');
        const { aceId }: { aceId: string } = await response.json();
        setAceId(aceId);
      } catch (_) {
        setAceId('Not available');
      }
    };
    fetchVersion();
  }, []);

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
          <Typography fontWeight="bold" as="span">
            Agent Compute ID:{' '}
          </Typography>
          {aceId}
          <br />
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
    from: '/$tenantId/$agentId',
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
