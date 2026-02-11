import { useCallback, useRef, useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { useSnackbar } from '@sema4ai/components';
import { useDeleteConfirm } from '@sema4ai/layouts';

import { DataConnectionFormSchema, SchemaFormItem } from '../../form';
import { buildSchemaFromFormData } from '../../schemaHelpers';
import { SchemaFormData } from '../components/SchemaForm';

type UseSchemaEditorOptions = {
  index: number | undefined;
  onDone: () => void;
};

export const useSchemaEditor = ({ index, onDone }: UseSchemaEditorOptions) => {
  const { watch, setValue } = useFormContext<DataConnectionFormSchema>();
  const { addSnackbar } = useSnackbar();
  const schemas = watch('schemas') || [];

  const formDataRef = useRef<SchemaFormData | null>(null);
  const [isFormValid, setIsFormValid] = useState(false);

  const isEditing = index !== undefined;
  const editingSchema: SchemaFormItem | undefined = isEditing ? schemas[index] : undefined;

  const handleFormDataChange = useCallback((data: SchemaFormData, isValid: boolean) => {
    formDataRef.current = data;
    setIsFormValid(isValid);
  }, []);

  const handleSave = useCallback(() => {
    const formData = formDataRef.current;
    if (!formData) return;

    try {
      const newSchema = buildSchemaFromFormData({ formData, existingSchema: editingSchema });
      const currentSchemas = schemas;

      if (index !== undefined) {
        const updatedSchemas = [...currentSchemas];
        updatedSchemas[index] = newSchema;
        setValue('schemas', updatedSchemas);
      } else {
        setValue('schemas', [...currentSchemas, newSchema]);
      }

      addSnackbar({
        message: isEditing ? 'Schema updated' : 'Schema added',
        variant: 'success',
      });
      onDone();
    } catch {
      addSnackbar({ message: 'Failed to save schema', variant: 'danger' });
    }
  }, [schemas, editingSchema, index, isEditing, setValue, addSnackbar, onDone]);

  const onDeleteConfirm = useDeleteConfirm(
    {
      entityName: editingSchema?.name,
      entityType: 'schema',
    },
    [editingSchema?.name],
  );

  const handleDelete = onDeleteConfirm(() => {
    if (index !== undefined) {
      const updatedSchemas = schemas.filter((_, i) => i !== index);
      setValue('schemas', updatedSchemas);
      onDone();
    }
  });

  return {
    editingSchema,
    handleFormDataChange,
    editorProps: {
      breadcrumb: 'Schemas',
      title: isEditing ? 'Edit Schema' : 'Add Schema',
      saveLabel: isEditing ? 'Save' : 'Add',
      isSaveDisabled: !isFormValid,
      isSaving: false as const,
      isEditing,
      onSave: handleSave,
      onDelete: handleDelete,
      onBack: onDone,
    },
  };
};
