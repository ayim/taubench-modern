import { FC, ReactNode } from 'react';
import { Box } from '@sema4ai/components';

type Props = {
  children?: ReactNode;
};

export const Content: FC<Props> = ({ children }) => {
  return <Box as="section">{children}</Box>;
};
