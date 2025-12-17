import { ChangeEvent, FC, useState } from 'react';
import { Input } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

type Props = {
  fieldName: string;
  initialValue?: string[];
};

export const SampleValuesField: FC<Props> = ({ fieldName, initialValue }: Props) => {
  const [value, updateValue] = useState(initialValue?.join(', ') ?? '');
  const { setValue } = useFormContext();

  const onSampleValuesChange = (e: ChangeEvent<HTMLInputElement>) => {
    const sampleValues = e.target.value
      .split(',')
      .map((curr) => curr.trim())
      .filter((curr) => curr !== '');
    setValue(fieldName, sampleValues);
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
