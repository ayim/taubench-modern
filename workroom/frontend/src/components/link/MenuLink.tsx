import { FC } from 'react';
import { Menu } from '@sema4ai/components';

import { useLinkProps, LinkProps } from './useLinkProps';

export const MenuLink: FC<LinkProps> = ({ to, params, preserveSubroute, children, ...rest }) => {
  const linkProps = useLinkProps(to, params, preserveSubroute);

  return (
    <Menu.Link {...linkProps} {...rest}>
      {children}
    </Menu.Link>
  );
};
