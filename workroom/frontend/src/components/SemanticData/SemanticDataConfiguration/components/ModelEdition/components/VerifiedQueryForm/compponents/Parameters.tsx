import { FC } from 'react';
import { Box, Checkbox, Input, Typography } from '@sema4ai/components';

import { QueryParameter } from '~/queries/semanticData';
import {
  applyQueryParameterName,
  applyQueryParameterValue,
  getQueryParameterValue,
} from '../../../../../../../../lib/SemanticDataModels';

type Props = {
  sql: string;
  parameters?: Array<QueryParameter>;
  onSqlChange: (sql: string) => void;
  onParametersChange: (parameters: Array<QueryParameter>) => void;
};

export const Parameters: FC<Props> = ({ parameters, onSqlChange, onParametersChange, sql }) => {
  if (!parameters || parameters.length === 0) {
    return null;
  }

  const selectedParameters = sql.match(/:(\w+)/g)?.map((match) => match.slice(1)) || [];

  const handleChange = (parameter: QueryParameter) => {
    if (selectedParameters.includes(parameter.name)) {
      onSqlChange(applyQueryParameterValue(sql, parameter));
    } else {
      onSqlChange(applyQueryParameterName(sql, parameter));
    }
  };

  return (
    <>
      <Typography variant="body-medium" fontWeight="medium">
        Parameters
      </Typography>
      {parameters.map((parameter) => {
        const isSelected = new RegExp(`:${parameter.name}\\b`).test(sql);
        const isDisabled = !isSelected && !sql.includes(getQueryParameterValue(parameter));

        return (
          <Box key={parameter.name}>
            <Checkbox
              label={parameter.name}
              checked={isSelected}
              onChange={() => handleChange(parameter)}
              disabled={isDisabled}
            />
            <Box pl="$24" pt="$4">
              <Input
                value={parameter.description}
                onChange={(e) =>
                  onParametersChange(
                    parameters.map((p) => (p.name === parameter.name ? { ...p, description: e.target.value } : p)),
                  )
                }
                type="text"
                aria-label={`Parameter ${parameter.name} description`}
              />
            </Box>
          </Box>
        );
      })}
    </>
  );
};
