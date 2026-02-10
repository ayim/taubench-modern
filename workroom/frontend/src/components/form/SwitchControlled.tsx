import { FC, ReactNode } from 'react';
import { useFormContext } from 'react-hook-form';
import { Switch } from '@sema4ai/components';

type ConnectedSwitchProps = {
  name: string;
  description?: ReactNode;
};

export const SwitchControlled: FC<ConnectedSwitchProps> = ({ name, description }) => {
  const { watch, setValue } = useFormContext();
  const value = watch(name);

  return (
    <Switch
      aria-label="connected label"
      checked={value || false}
      onChange={(newValue) => setValue(name, newValue)}
      description={description}
    />
  );
};
