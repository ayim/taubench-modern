import { ChangeEvent, FC, useState } from 'react';
import { Input } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { DataConnectionFormSchema } from '../../form';

type Props = {
  tableIndex: number;
  dimensionIndex: number;
  initialValue?: string[];
};
export const SampleValuesField: FC<Props> = ({ tableIndex, dimensionIndex, initialValue }: Props) => {
  const [value, updateValue] = useState(initialValue?.join(', ') ?? '');
  const { setValue } = useFormContext<DataConnectionFormSchema>();

  const onSampleValuesChange = (e: ChangeEvent<HTMLInputElement>) => {
    const sampleValues = e.target.value
      .split(',')
      .map((curr) => curr.trim())
      .filter((curr) => curr !== '');
    setValue(`tables.${tableIndex}.dimensions.${dimensionIndex}.sample_values`, sampleValues);
    updateValue(sampleValues.join(', '));
  };

  return (
    <Input
      aria-label="Sample Values"
      variant="ghost"
      value={value}
      onChange={(e) => updateValue(e.target.value)}
      onBlur={onSampleValuesChange}
      autoGrow={8}
    />
  );
};
