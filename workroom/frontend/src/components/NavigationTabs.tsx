import { FC } from 'react';
import { Link, LinkProps, useRouterState } from '@tanstack/react-router';
import { Tabs, TabsProps } from '@sema4ai/components';

export type NavigationTab = Pick<LinkProps, 'to'> & { label: string; count?: string; hidden?: boolean };

type Props = {
  tabs: NavigationTab[];
  actions?: TabsProps['actions'];
};

export const NavigationTabs: FC<Props> = ({ tabs, actions }) => {
  const state = useRouterState();

  const visibleTabs = tabs.filter((tab) => !tab.hidden);

  const activeTabIndex = visibleTabs.findIndex(
    (tab) => state.matches.findIndex((match) => match.routeId === tab.to) > -1,
  );
  const activeTab = activeTabIndex === -1 ? undefined : activeTabIndex;

  return (
    <Tabs activeTab={activeTab} setActiveTab={() => null} actions={actions}>
      {visibleTabs.map((tab) => {
        return (
          <Tabs.Tab
            key={tab.to}
            forwardedAs={Link}
            to={tab.to}
            activeOptions={{ exact: true, includeSearch: false }}
            badgeLabel={tab.count}
          >
            {tab.label}
          </Tabs.Tab>
        );
      })}
    </Tabs>
  );
};
