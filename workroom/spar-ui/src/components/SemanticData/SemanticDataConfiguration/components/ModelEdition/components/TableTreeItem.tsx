import { FC } from 'react';
import { TreeList } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { IconDbColumn } from '@sema4ai/icons';

import { Dimension } from '../../../../../../queries';
import { InputControlled } from '../../../../../../common/form/InputControlled';
import { SynonymField } from './SynonymField';

type Props = {
  tableIndex: number;
  dimensionIndex: number;
  type: string;
  dimension: Dimension;
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

export const TableTreeItem: FC<Props> = ({ tableIndex, dimensionIndex, type, dimension }) => {
  return (
    <TreeList.Item
      key={dimension.name}
      label={dimension.name}
      icon={IconDbColumn}
      description={`${dimension.expr} • ${dimension.data_type.replace('!', '')}  `}
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
        </>
      }
    />
  );
};
