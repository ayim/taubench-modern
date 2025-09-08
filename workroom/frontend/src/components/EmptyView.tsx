import { FC, ReactNode } from 'react';
import { Box, EmptyState, Link } from '@sema4ai/components';
import { IconArrowUpRight, IconInformation } from '@sema4ai/icons';

import { Illustration, IllustrationName } from './Illustration';
import { EXTERNAL_LINKS } from '../config/externalLinks';

type Props = {
  title: string;
  description: string;
  action?: ReactNode;
  illustration: IllustrationName;
  docsLink: keyof typeof EXTERNAL_LINKS;
};

export const EmptyView: FC<Props> = ({ description, title, illustration, docsLink, action }) => {
  return (
    <Box display="flex" flex="1" justifyContent="center" flexDirection="column" maxHeight={960} height="100%">
      <EmptyState
        illustration={<Illustration name={illustration} />}
        title={title}
        description={description}
        action={action}
        secondaryAction={
          <Link
            icon={IconInformation}
            iconAfter={IconArrowUpRight}
            href={EXTERNAL_LINKS[docsLink]}
            target="_blank"
            rel="noopener"
            variant="secondary"
            fontWeight="medium"
          >
            Learn more
          </Link>
        }
      />
    </Box>
  );
};
