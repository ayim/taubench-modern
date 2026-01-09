import { FC } from 'react';
import { Link as LinkBase, LinkProps as LinkComponentProps } from '@sema4ai/components';

import { useLinkProps, LinkProps } from './useLinkProps';

export const Link: FC<LinkProps & LinkComponentProps> = ({ to, params, preserveSubroute, children, ...rest }) => {
  const linkProps = useLinkProps(to, params, preserveSubroute);

  return (
    <LinkBase {...linkProps} {...rest}>
      {children}
    </LinkBase>
  );
};
