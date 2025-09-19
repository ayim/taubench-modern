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

  const activeTab = tabs.findIndex((tab) => state.matches.findIndex((match) => match.routeId === tab.to) > -1);

  return (
    <Tabs activeTab={activeTab} setActiveTab={() => null} actions={actions}>
      {tabs.map((tab) => {
        return (
          !tab.hidden && (
            <Tabs.Tab
              key={tab.to}
              forwardedAs={Link}
              to={tab.to}
              activeOptions={{ exact: true, includeSearch: false }}
              badgeLabel={tab.count}
            >
              {tab.label}
            </Tabs.Tab>
          )
        );
      })}
    </Tabs>
  );
};
