import { FC } from 'react';

type CommonProps = {
  messageId: string;
};

export type InteractionComponent<T extends { type: string }> = FC<CommonProps & { payload: T }>;
