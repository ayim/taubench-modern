import { Box, Progress } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';

/**
 * Inline Loader
 * Use when a View container is displayed, but the content is not ready yet
 */
export const InlineLoader = () => {
  return (
    <Box
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      minHeight="100%"
      maxWidth={480}
      margin="0 auto"
    >
      <Progress />
    </Box>
  );
};

const InlineContainer = styled.div`
  position: fixed;
  top: 0px;
  left: 0px;
  height: 200px;
  width: 100%;
  z-index: ${({ theme }) => theme.zIndex.focus};
  > div {
    height: 2px;
  }
`;

/**
 * Transition Loader
 * Use when a View is not shown until the content is not ready
 */
export const TransitionLoader = () => {
  return (
    <InlineContainer>
      <Progress variant="page" />
    </InlineContainer>
  );
};
