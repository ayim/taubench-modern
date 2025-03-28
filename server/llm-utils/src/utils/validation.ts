type ValidationField = {
  value: any;
  fieldName: string;
};

export const validateRequiredFields = (fields: ValidationField[]): string[] | null => {
  const missingFields = fields.filter((field) => !field.value).map((field) => field.fieldName);

  if (missingFields.length > 0) {
    return missingFields;
  }

  return null;
};
