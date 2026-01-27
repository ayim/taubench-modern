import { ForwardedRef, forwardRef, HTMLAttributes } from 'react';
import { createLink } from '@tanstack/react-router';
import {
  Button as ButtonBase,
  ButtonProps,
  Card,
  Link as LinkBase,
  LinkProps,
  Menu,
  SideNavigation,
} from '@sema4ai/components';
import type { SideNavigationLinkProps } from '@sema4ai/components';
import { IconType } from '@sema4ai/icons';

/**
 * Design System `Link` component wrapped as Tanstack Router Link
 */
export const RouterLink = createLink(
  forwardRef<HTMLAnchorElement, LinkProps>((props, ref) => {
    return <LinkBase {...props} ref={ref} />;
  }),
);

/**
 * Design System `Button` component wrapped as Tanstack Router Link
 */
export const RouterButton = createLink(
  forwardRef(
    (
      props: HTMLAttributes<HTMLAnchorElement> & Omit<ButtonProps, keyof HTMLAttributes<HTMLButtonElement>>,
      ref: ForwardedRef<HTMLAnchorElement>,
    ) => {
      return <ButtonBase forwardedAs="a" {...props} ref={ref} />;
    },
  ),
);

/**
 * Design System `Menu.Link` component wrapped as Tanstack Router Link
 */
export const RouterMenuLink = createLink(
  forwardRef<HTMLAnchorElement, LinkProps & { onClick?: () => void }>((props, ref) => {
    return <Menu.Link {...props} ref={ref} />;
  }),
);

export const RouterSideNavigationLink = createLink(
  forwardRef<HTMLAnchorElement, SideNavigationLinkProps & { onClick?: () => void }>((props, ref) => {
    return <SideNavigation.Link {...props} ref={ref} />;
  }),
);

type CardLinkProps = {
  title: string;
  icon: IconType;
  description: string;
};

export const RouterCardLink = createLink(
  forwardRef<HTMLDivElement, CardLinkProps>((props, ref) => {
    return <Card as="a" {...props} ref={ref} />;
  }),
);
