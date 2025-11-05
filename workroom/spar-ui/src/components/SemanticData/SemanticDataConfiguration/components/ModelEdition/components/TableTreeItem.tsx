import { FC } from 'react';
import { TreeList } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { IconDbColumn } from '@sema4ai/icons';
import { Typography } from '@sema4ai/components';

import { Dimension } from '../../../../../../queries';
import { InputControlled } from '../../../../../../common/form/InputControlled';
import { SynonymField } from './SynonymField';
import { SampleValuesField } from './SampleValuesField';
import { ServerResponse } from '../../../../../../queries/shared';

type Props = {
  tableIndex: number;
  dimensionIndex: number;
  type: string;
  dimension: Dimension;
  validation?: ServerResponse<'post', '/api/v2/semantic-data-models/validate'>['results'][number];
};

const Cell = styled.div`
  label {
    display: block;
    height: 100%;

    > div {
      height: 100%;
    }

    textarea {
      min-height: 100%;
    }
  }
`;

// TODO: This is a temporary solution on how to parse an error for exact dimension, Agent Server should return the errors more structured
const getDimensionError = (validation: Props['validation'], dimension: Dimension) => {
  if (!validation?.errors) {
    return undefined;
  }

  const hasNotFoundError = validation?.errors?.some((error) =>
    error.message.includes(`Column '${dimension.expr}' is not found in table`),
  );

  if (hasNotFoundError) {
    return 'Column not found in table';
  }

  return undefined;
};

export const TableTreeItem: FC<Props> = ({ tableIndex, dimensionIndex, type, dimension, validation }) => {
  const error = getDimensionError(validation, dimension);

  const description = (
    <>
      {`${dimension.expr} • ${dimension.data_type.replace('!', '')}  `}{' '}
      {error && (
        <>
          <br />
          <Typography color="content.error">{error}</Typography>
        </>
      )}
    </>
  );

  return (
    <TreeList.Item
      key={dimension.name}
      label={dimension.name}
      icon={IconDbColumn}
      description={description}
      columns={
        <>
          <Cell>
            <InputControlled
              fieldName={`tables.${tableIndex}.${type}.${dimensionIndex}.description`}
              aria-label="Description"
              variant="ghost"
              autoGrow={8}
            />
          </Cell>
          <Cell>
            <SynonymField tableIndex={tableIndex} dimensionIndex={dimensionIndex} initialValue={dimension.synonyms} />
          </Cell>
          <Cell>
            <SampleValuesField
              tableIndex={tableIndex}
              dimensionIndex={dimensionIndex}
              initialValue={dimension.synonyms}
            />
          </Cell>
        </>
      }
    />
  );
};
