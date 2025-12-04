import { useContext, useState } from 'react';
import { Box, Checkbox, Input } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { DataConnectionFormContext, DataConnectionFormSchema } from '../../form';

export const BusinessContext = () => {
  const { register } = useFormContext<DataConnectionFormSchema>();
  const { forceModelRegeneration, setForceModelRegeneration } = useContext(DataConnectionFormContext);
  const [skipChangeCheck, setSkipChangeCheck] = useState(false);

  const onToggleForceModelRegeneration = () => {
    if (forceModelRegeneration) {
      setSkipChangeCheck(true);
    }

    setForceModelRegeneration(!forceModelRegeneration);
  };

  const inputProps = register('description', {
    onChange: () => {
      if (!skipChangeCheck) {
        setForceModelRegeneration(true);
      }
    },
  });

  return (
    <Box display="flex" flexDirection="column" gap="$8" maxWidth={720}>
      <Input rows={20} {...inputProps} placeholder="Enter business context..." aria-label="Business Context" />
      <Checkbox
        label="Re-create Data Model"
        description="Generates a new model based on the latest changes and overwrites existing details."
        checked={forceModelRegeneration}
        onChange={onToggleForceModelRegeneration}
      />
    </Box>
  );
};
