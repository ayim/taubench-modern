import { ListSkeleton, SkeletonLoader } from '@sema4ai/components';

import { InteractionComponent } from './shared';

export type LoadingPayload = {
  type: 'loading';
};

export const Loading: InteractionComponent<LoadingPayload> = () => {
  return <SkeletonLoader skeleton={ListSkeleton} loading />;
};
