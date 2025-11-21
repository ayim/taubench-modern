import { FC, ReactNode } from 'react';
import { Box, Tooltip, Typography } from '@sema4ai/components';
import { IconHelpSmall } from '@sema4ai/icons';

type Props = {
  children?: ReactNode;
};

/*
 TODO: Scoring is disable until Agent Server is updated to return the actual scoring
const scoringMeta: { min: number; max: number; label: string; backgroundColor: Color; borderColor: Color }[] = [
  {
    min: 0,
    max: 25,
    label: 'Poor',
    backgroundColor: 'red30',
    borderColor: 'red80',
  },
  {
    min: 26,
    max: 50,
    label: 'Fair',
    backgroundColor: 'orange30',
    borderColor: 'orange80',
  },
  {
    min: 51,
    max: 95,
    label: 'Good',
    backgroundColor: 'orange30',
    borderColor: 'orange80',
  },
  {
    min: 96,
    max: 100,
    label: 'Excellent',
    backgroundColor: 'green30',
    borderColor: 'green80',
  },
];
*/

export const ModelScore: FC<Props> = ({ children }) => {
  return (
    <Box
      display="flex"
      gap="$36"
      flex="1"
      backgroundColor="background.panels"
      p="$20"
      borderColor="border.subtle"
      borderWidth={1}
      borderRadius="$16"
    >
      <Box flex="1">
        <Box display="flex" alignItems="center" gap="$8" mb="$4">
          <Typography color="content.subtle.light">Data Understanding</Typography>
          <Tooltip text="The data understanding score is a measure of how well the data model captures the data.">
            <IconHelpSmall color="background.subtle" />
          </Tooltip>
        </Box>
        <Typography fontWeight="medium" mb="$8">
          Coming soon!
        </Typography>
        <Box height="$8" borderRadius="$8" backgroundColor="background.disabled" />
      </Box>
      {children && (
        <Box display="flex" alignItems="center" justifyContent="flex-end">
          {children}
        </Box>
      )}
    </Box>
  );
};
