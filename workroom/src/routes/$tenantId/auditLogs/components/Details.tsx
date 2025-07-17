import { ReactNode } from 'react';
import { styled } from '@sema4ai/theme';
import { componentWithRef } from '@sema4ai/components';

type Props = {
  children?: ReactNode;
};

const Container = styled.dl`
  display: grid;
  grid-template-columns: max-content 1fr;
  row-gap: ${({ theme }) => theme.space.$4};
  column-gap: ${({ theme }) => theme.space.$16};
`;

const Label = styled.dt`
  text-align: right;
  font-weight: ${({ theme }) => theme.fontWeights.medium};
  color: ${({ theme }) => theme.colors.content.subtle.color};
`;

const Content = styled.dd``;

const compoundComponents = {
  Label,
  Content,
};

export const Details = componentWithRef<Props, HTMLDListElement, typeof compoundComponents>(
  ({ children }, forwardRef) => {
    return <Container ref={forwardRef}>{children}</Container>;
  },
  compoundComponents,
);
