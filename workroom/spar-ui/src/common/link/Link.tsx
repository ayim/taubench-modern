import { FC } from 'react';
import { Link as LinkBase, LinkProps as LinkComponentProps } from '@sema4ai/components';

import { useLinkProps, LinkProps } from './useLinkProps';

export const Link: FC<LinkProps & LinkComponentProps> = ({ to, params, children, ...rest }) => {
  const linkProps = useLinkProps(to, params);

  return (
    <LinkBase {...linkProps} {...rest}>
      {children}
    </LinkBase>
  );
};
