import { ChangeEvent, FC, useCallback, useMemo, useRef, useState } from 'react';
import { Input, InputProps } from '@sema4ai/components';
import { IconEye, IconEyeLock } from '@sema4ai/icons';
import { Controller, useFormContext } from 'react-hook-form';

type Props = InputProps & {
  fieldName: string;
  errorMessage?: string;
};

export const InputControlled: FC<Props> = ({ fieldName, errorMessage, type, ...rest }) => {
  const [showSecretValue, setShowSecretValue] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { control } = useFormContext();

  const onToggleHideInputValue = () => {
    setShowSecretValue((state) => !state);
  };

  const fieldProps = useMemo(() => {
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
  }, [showSecretValue, type]);

  const onChange = useCallback(
    (cb: (value: string | number | undefined) => void) => (e: ChangeEvent<HTMLInputElement>) => {
      if (type === 'number') {
        const value = e.target.value.length ? Number(e.target.value) : undefined;
        return cb(value);
      }
      return cb(e.target.value);
    },
    [type],
  );

  return (
    <Controller
      control={control}
      name={fieldName}
      render={({ field, fieldState: { error } }) => (
        <Input
          {...field}
          {...rest}
          {...fieldProps}
          ref={inputRef}
          onChange={onChange(field.onChange)}
          error={(error && errorMessage) || error?.message}
        />
      )}
    />
  );
};
