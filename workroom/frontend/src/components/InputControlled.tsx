import { Input, InputProps } from '@sema4ai/components';
import { IconEye, IconEyeLock } from '@sema4ai/icons';
import { ChangeEvent, FC, useState } from 'react';
import { Controller, useFormContext } from 'react-hook-form';

type Props = InputProps & {
  fieldName: string;
  errorMessage?: string;
};

export const InputControlled: FC<Props> = ({ fieldName, errorMessage, type, ...rest }) => {
  const [showSecretValue, setShowSecretValue] = useState(false);
  const { control } = useFormContext();

  const onToggleHideInputValue = () => {
    setShowSecretValue((state) => !state);
  };

  const getFieldProps = () => {
    if (type === 'number') {
      return {
        type: 'number',
      };
    }

    if (type === 'password') {
      return {
        type: showSecretValue ? 'text' : 'password',
        iconRight: showSecretValue ? IconEyeLock : IconEye,
        iconRightLabel: 'Toggle input visibility',
        onIconRightClick: onToggleHideInputValue,
      };
    }

    return {};
  };

  const handleChange = (cb: (value: string | number | undefined) => void) => (e: ChangeEvent<HTMLInputElement>) => {
    if (type === 'number') {
      const value = e.target.value.length ? Number(e.target.value) : undefined;
      return cb(value);
    }
    return cb(e.target.value);
  };

  return (
    <Controller
      control={control}
      name={fieldName}
      render={({ field, fieldState: { error } }) => (
        <Input
          {...field}
          {...rest}
          {...getFieldProps()}
          onChange={handleChange(field.onChange)}
          error={(error && errorMessage) || error?.message}
        />
      )}
    />
  );
};
