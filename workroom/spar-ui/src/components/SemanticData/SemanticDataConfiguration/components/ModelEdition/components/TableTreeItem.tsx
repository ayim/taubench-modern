import { FC } from 'react';
import { TreeList } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { IconCloseSmall, IconDbColumn } from '@sema4ai/icons';
import { Button, Typography } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { Dimension } from '../../../../../../queries';
import { InputControlled } from '../../../../../../common/form/InputControlled';
import { SynonymField } from './SynonymField';
import { SampleValuesField } from './SampleValuesField';
import { ServerResponse } from '../../../../../../queries/shared';
import { DataConnectionFormSchema } from '../../form';

type Props = {
  tableIndex: number;
  dimensionIndex: number;
  type: 'dimensions' | 'time_dimensions' | 'facts' | 'metrics';
  dimensions: Dimension[];
  validation?: ServerResponse<'post', '/api/v2/semantic-data-models/validate'>['results'][number];
  baseTableName: string;
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

export const TableTreeItem: FC<Props> = ({
  baseTableName,
  tableIndex,
  dimensionIndex,
  type,
  dimensions,
  validation,
}) => {
  const { setValue, watch } = useFormContext<DataConnectionFormSchema>();
  const dataSelection = watch('dataSelection');

  const dimension = dimensions[dimensionIndex];
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

  const handleRemoveDimension = () => {
    const newDimensions = [...dimensions];
    newDimensions.splice(dimensionIndex, 1);
    setValue(`tables.${tableIndex}.${type}`, newDimensions);

    const dataSlectionTableIndex = dataSelection.findIndex((selection) => selection.name === baseTableName);
    const newDataSelection = [...dataSelection];
    newDataSelection[dataSlectionTableIndex].columns = newDataSelection[dataSlectionTableIndex].columns.filter(
      (column) => column.name !== dimension.name,
    );
    setValue('dataSelection', newDataSelection);
  };

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
          <Cell>
            <Button
              variant="ghost-subtle"
              aria-label="Remove dimension"
              icon={IconCloseSmall}
              onClick={handleRemoveDimension}
            />
          </Cell>
        </>
      }
    />
  );
};
