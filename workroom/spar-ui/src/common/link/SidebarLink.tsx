import { FC } from 'react';
import { styled } from '@sema4ai/theme';

import { useLinkProps, LinkProps } from './useLinkProps';

const SidebarLinkBase = styled.a`
  line-height: ${({ theme }) => theme.sizes.$36};
  color: ${({ theme }) => theme.colors.content.subtle.light.color};
  padding: 0 ${({ theme }) => theme.space.$8};
  text-decoration: none;

  &:hover {
    color: ${({ theme }) => theme.colors.content.primary.color};
  }

  &[aria-current='page'] {
    color: ${({ theme }) => theme.colors.content.subtle.light.hovered.color};
    font-weight: ${({ theme }) => theme.fontWeights.medium};
  }
`;

export const SidebarLink: FC<LinkProps> = ({ to, params, children }) => {
  const linkProps = useLinkProps(to, params);

  return <SidebarLinkBase {...linkProps}>{children}</SidebarLinkBase>;
};
