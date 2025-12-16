import { ComponentProps, FC } from 'react';
import { styled } from '@sema4ai/theme';
import { List } from '@sema4ai/components';

import { useLinkProps, LinkProps } from './useLinkProps';

const StyledListLink = styled(List.Link)`
  > div > p {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
`;

export const ListItemLink: FC<Omit<LinkProps, 'children'> & ComponentProps<typeof List.Link>> = ({
  to,
  params,
  children,
  ...navigationLinkProps
}) => {
  const linkProps = useLinkProps(to, params);

  return (
    <StyledListLink {...navigationLinkProps} {...linkProps} aria-current={linkProps['aria-current'] ? true : undefined}>
      {children}
    </StyledListLink>
  );
};
