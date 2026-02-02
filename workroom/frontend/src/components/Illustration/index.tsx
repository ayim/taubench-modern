import { useTheme } from '@sema4ai/components';
import { FC } from 'react';

/**
 * Illustrations are located in the ./public/illustrations folder.
 */
type IllustrationName =
  | 'actions'
  | 'agents'
  | 'documents_processing'
  | 'environments'
  | 'generic'
  | 'llms'
  | 'secrets'
  | 'evals';

type Props = {
  name: IllustrationName;
};

export const Illustration: FC<Props> = ({ name }) => {
  const { name: themeName } = useTheme();
  return <img src={`illustrations/${name}-${themeName}.svg`} alt={name} loading="lazy" />;
};
