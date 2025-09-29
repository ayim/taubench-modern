import { Box, EmptyState, Progress } from '@sema4ai/components';
import { Illustration } from "../components/Illustration";
import { ButtonLink } from "../common/link";

export const useQueryDataGuard = (queryData: { isLoading: boolean; isError: boolean }[]) => {
  if (queryData.some(({ isLoading }) => isLoading)) {
    return <Progress variant="page" />;
  }

  if (queryData.some(({ isError }) => isError)) {
     return (
    <Box
      as="section"
      display="flex"
      justifyContent="center"
      flexDirection="column"
      maxHeight={960}
      height="100%"
      
    >
      <EmptyState
        illustration={<Illustration name="generic" />}
        title="Agent Deployment not found"
        description="The resource you are looking for was not found."
        action={
          <ButtonLink to="/home" params={{}} round>
            Return to Agents
          </ButtonLink>
        }
      />
    </Box>
  );
  }

  return undefined;
};
