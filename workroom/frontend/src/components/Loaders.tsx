import { Box, Progress } from '@sema4ai/components';

/**
 * Full screen progress loading state indicator
 * Used only when the whole page is in a loading state (i.e. initial application boot or auth callback endpoints)
 */
export const FullScreenLoader = () => {
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
