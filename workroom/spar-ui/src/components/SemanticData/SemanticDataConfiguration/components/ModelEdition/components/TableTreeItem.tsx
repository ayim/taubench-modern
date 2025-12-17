import { FC } from 'react';
import { TreeList } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { IconCloseSmall, IconDbColumn } from '@sema4ai/icons';
import { Button, Typography } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { Dimension, SemanticModel } from '../../../../../../queries';
import { InputControlled } from '../../../../../../common/form/InputControlled';
import { SynonymField } from './SynonymField';
import { SampleValuesField } from './SampleValuesField';
import { DataConnectionFormSchema } from '../../form';

type Props = {
  tableIndex: number;
  dimensionIndex: number;
  errors?: SemanticModel['tables'][number]['errors'];
  type: 'dimensions' | 'time_dimensions' | 'facts' | 'metrics';
  dimensions: Dimension[];
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

export const TableTreeItem: FC<Props> = ({ baseTableName, tableIndex, dimensionIndex, type, dimensions, errors }) => {
  const { setValue, watch } = useFormContext<DataConnectionFormSchema>();
  const dataSelection = watch('dataSelection');

  const dimension = dimensions[dimensionIndex];

  const description = (
    <>
      {`${dimension.expr || 'No name'} • ${dimension.data_type.replace('!', '')}  `}{' '}
      {errors && (
        <>
          <br />
          <Typography color="content.error">{errors.map((error) => error.message).join(', ')}</Typography>
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
      (column) => column.name !== dimension.expr,
    );
    setValue('dataSelection', newDataSelection);
  };

  return (
    <TreeList.Item
      key={dimension.name}
      label={dimension.name || <Typography color="content.subtle.light">No name</Typography>}
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
            <SynonymField
              fieldName={`tables.${tableIndex}.${type}.${dimensionIndex}.synonyms`}
              initialValue={dimension.synonyms}
            />
          </Cell>
          <Cell>
            <SampleValuesField
              fieldName={`tables.${tableIndex}.${type}.${dimensionIndex}.sample_values`}
              initialValue={dimension.sample_values}
            />
          </Cell>
          <Cell>
            {dimensions.length > 1 && (
              <Button
                variant="ghost-subtle"
                aria-label="Remove dimension"
                icon={IconCloseSmall}
                onClick={handleRemoveDimension}
              />
            )}
          </Cell>
        </>
      }
    />
  );
};
