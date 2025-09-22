import { FC, useEffect } from 'react';
import { useFormContext } from 'react-hook-form';
import { Select, SelectProps } from '@sema4ai/components';
import { IconCloseSmall } from '@sema4ai/icons';

interface ConnectedSelectProps extends Omit<SelectProps, 'name'> {
  name: string;
  errorMessage?: string;
  onClear?: () => void;
  onMounted?: () => void;
}

export const SelectControlled: FC<ConnectedSelectProps> = ({ onClear, name, errorMessage, onMounted, ...rest }) => {
  const { watch, setValue, formState } = useFormContext();
  const value = watch(name);
  const error = formState.errors[name];

  useEffect(() => {
    onMounted?.();
  }, []);

  return (
    <Select
      aria-label="connected label"
      value={value || ''}
      error={(error && errorMessage) || (error?.message as string)}
      onChange={(newValue) => setValue(name, newValue)}
      iconRightSecondary={onClear && value != null ? IconCloseSmall : undefined}
      onIconRightSecondaryClick={onClear}
      iconRightSecondaryLabel="Clear value"
      {...rest}
    />
  );
};
