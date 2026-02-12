import { SchemaFormData } from './ModelEdition/components/SchemaForm';
import { SchemaFormItem } from './form';

export const normalizeSchemaName = (name: string): string => {
  return name.trim().replace(/ /g, '_');
};

export const isValidSchemaName = (name: string): boolean => {
  return /^[a-zA-Z0-9_ ]*$/.test(name);
};

export const buildSchemaFromFormData = ({
  formData,
  existingSchema,
}: {
  formData: SchemaFormData;
  existingSchema?: SchemaFormItem;
}): SchemaFormItem => {
  const parsed = JSON.parse(formData.jsonText);
  return {
    name: normalizeSchemaName(formData.name),
    description: formData.description.trim(),
    json_schema: parsed,
    validations: existingSchema?.validations || [],
    transformations: existingSchema?.transformations || [],
    document_extraction: formData.useDocumentExtraction
      ? {
          system_prompt: formData.systemPrompt.trim(),
          configuration: formData.configurationText.trim() ? JSON.parse(formData.configurationText) : {},
        }
      : undefined,
  };
};
