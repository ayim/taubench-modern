import { ChangeEvent, FC, useState } from 'react';
import { Input } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { DataConnectionFormSchema } from '../../form';

type Props = {
  tableIndex: number;
  dimensionIndex: number;
  initialValue?: string[];
};
export const SynonymField: FC<Props> = ({ tableIndex, dimensionIndex, initialValue }: Props) => {
  const [value, updateValue] = useState(initialValue?.join(', ') ?? '');
  const { setValue } = useFormContext<DataConnectionFormSchema>();

  const onSynonymsChange = (e: ChangeEvent<HTMLInputElement>) => {
    const synonyms = e.target.value
      .split(',')
      .map((curr) => curr.trim())
      .filter((curr) => curr !== '');
    setValue(`tables.${tableIndex}.dimensions.${dimensionIndex}.synonyms`, synonyms);
    updateValue(synonyms.join(', '));
  };

  return (
    <Input
      aria-label="Synonyms"
      variant="ghost"
      value={value}
      onChange={(e) => updateValue(e.target.value)}
      onBlur={onSynonymsChange}
      autoGrow={8}
    />
  );
};
