import { FC } from 'react';
import { Button, ButtonProps } from '@sema4ai/components';

import { useLinkProps, LinkProps } from './useLinkProps';

type SelectedButtonProps = Pick<ButtonProps, 'variant' | 'round' | 'icon'>;

export const ButtonLink: FC<LinkProps & SelectedButtonProps> = ({
  to,
  params,
  preserveSubroute,
  children,
  ...rest
}) => {
  const linkProps = useLinkProps(to, params, preserveSubroute);

  return (
    <Button forwardedAs="a" {...linkProps} {...rest}>
      {children}
    </Button>
  );
};
