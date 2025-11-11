import { FC, ReactNode } from 'react';
import { useFormContext } from 'react-hook-form';
import { Box, Tooltip, Typography } from '@sema4ai/components';
import { IconHelpSmall } from '@sema4ai/icons';
import { Color } from '@sema4ai/theme';

import { DataConnectionFormSchema } from '../../form';
import { getTableDimensions } from '../../../../../../lib/SemanticDataModels';

type Props = {
  children?: ReactNode;
};

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

export const ModelScore: FC<Props> = ({ children }) => {
  const { watch } = useFormContext<DataConnectionFormSchema>();

  const { tables } = watch();

  // TODO: This is a very rudimentary scoring, should be upodated with a backend solution for actual quality score
  const modelScore = (() => {
    const score = tables?.reduce<{ total: number; filled: number }>(
      (acc, table) => {
        const dimensions = getTableDimensions(table);

        const total = acc.total + dimensions.length * 2;
        const filled =
          acc.filled +
          dimensions.filter((dimension) => dimension.description).length +
          dimensions.filter((dimension) => dimension.synonyms && dimension.synonyms?.length > 0).length;

        return { total, filled };
      },
      { total: 0, filled: 0 },
    ) || { total: 0, filled: 0 };

    const finalScore = Math.round((score.filled / score.total) * 100);
    const meta = scoringMeta.find((curr) => finalScore >= curr.min && finalScore <= curr.max);

    return { finalScore, ...meta };
  })();

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
          {modelScore.label}
        </Typography>
        <Box height="$8" borderRadius="$8" backgroundColor={modelScore.backgroundColor}>
          <Box
            height="100%"
            borderRadius="$8"
            width={`${modelScore.finalScore}%`}
            backgroundColor={modelScore.borderColor}
          />
        </Box>
      </Box>
      {children && (
        <Box display="flex" alignItems="center" justifyContent="flex-end">
          {children}
        </Box>
      )}
    </Box>
  );
};
