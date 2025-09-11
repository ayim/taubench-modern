import { FC } from 'react';
import { useTheme } from '@sema4ai/components';

/**
 * Illustrations are located in the ./public/illustrations folder.
 */
export type IllustrationName = 'agents' | 'generic' | 'llms' | 'secrets';

type Props = {
  name: IllustrationName;
};

export const Illustration: FC<Props> = ({ name }) => {
  const { name: themeName } = useTheme();
  return <img src={`illustrations/${name}-${themeName}.svg`} alt={name} loading="lazy" />;
};
