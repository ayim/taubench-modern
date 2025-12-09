import { FC, useMemo } from 'react';

import { Code } from '../../../../../common/code';
import { QuickOptions, QuickOptionsPayload } from './QuickOptions';
import { Loading, LoadingPayload } from './Loading';

type Props = {
  content: string;
  messageId: string;
};

type InteractionSpec = QuickOptionsPayload | LoadingPayload;

export const InteractionComponent: FC<Props> = ({ content, messageId }) => {
  const payload = useMemo<InteractionSpec>(() => {
    try {
      return JSON.parse(content);
    } catch {
      return {
        type: 'loading',
      };
    }
  }, [content]);

  switch (payload.type) {
    case 'quick-options':
      return <QuickOptions payload={payload} messageId={messageId} />;
    case 'loading':
      return <Loading payload={payload} messageId={messageId} />;
    default:
      return <Code value={content} rows={10} />;
  }
};
