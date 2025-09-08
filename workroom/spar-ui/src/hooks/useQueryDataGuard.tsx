import { Progress } from '@sema4ai/components';

export const useQueryDataGuard = (queryData: { isLoading: boolean; isError: boolean }[]) => {
  if (queryData.some(({ isLoading }) => isLoading)) {
    return <Progress variant="page" />;
  }

  if (queryData.some(({ isError }) => isError)) {
    return <>TODO-V2: Display Error page</>;
  }

  return undefined;
};
