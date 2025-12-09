import { useState, useCallback } from 'react';

export type AnnotationType = 'text' | 'field' | 'table' | 'drawing';

export interface Annotation {
  id: string;
  type: AnnotationType;
  pageNumber: number;
  left: number;
  top: number;
  width: number;
  height: number;
  comment: string;
  fieldName?: string;
  fieldValue?: string;
  selectedText?: string;
  createdAt: string;
  updatedAt?: string;
}

export interface FieldMapping {
  id: string;
  name: string;
  value: string;
  annotationId?: string;
  enabled: boolean;
}

export const generateUniqueId = (prefix?: string): string => {
  const formattedPrefix = prefix ? prefix.toLowerCase().replace(/ /g, '-') : 'field';
  return `${formattedPrefix}-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
};

export const usePdfAnnotations = () => {
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [editingAnnotation, setEditingAnnotation] = useState<Annotation | null>(null);
  const [editComment, setEditComment] = useState<string>('');
  const [editFieldName, setEditFieldName] = useState<string>('');
  const [editFieldValue, setEditFieldValue] = useState<string>('');
  const [fields, setFields] = useState<FieldMapping[]>([]);
  const [showAnnotationPopup, setShowAnnotationPopup] = useState<boolean>(false);
  const [pendingAnnotation, setPendingAnnotation] = useState<Partial<Annotation> | null>(null);

  const addAnnotation = useCallback((annotation: Omit<Annotation, 'id' | 'createdAt'>) => {
    const newAnnotation: Annotation = {
      ...annotation,
      id: generateUniqueId('annotation'),
      createdAt: new Date().toISOString(),
    };
    setAnnotations((prev) => [...prev, newAnnotation]);

    return newAnnotation;
  }, []);

  const addField = useCallback((field: Partial<FieldMapping> & { name: string; value: string }) => {
    const newField: FieldMapping = {
      id: generateUniqueId('field'),
      name: field.name,
      value: field.value,
      annotationId: field.annotationId,
      enabled: field.enabled ?? true,
    };
    setFields((prev) => [...prev, newField]);
    return newField;
  }, []);

  const updateField = useCallback((fieldId: string, updates: Partial<FieldMapping>) => {
    setFields((prev) => prev.map((field) => (field.id === fieldId ? { ...field, ...updates } : field)));
  }, []);

  const deleteField = useCallback((fieldId: string) => {
    setFields((prev) => prev.filter((field) => field.id !== fieldId));
  }, []);

  const updateAnnotation = useCallback((annotationId: string, updates: Partial<Annotation>) => {
    setAnnotations((prev) =>
      prev.map((ann) => (ann.id === annotationId ? { ...ann, ...updates, updatedAt: new Date().toISOString() } : ann)),
    );
  }, []);

  const deleteAnnotation = useCallback((annotationId: string) => {
    setAnnotations((prev) => prev.filter((ann) => ann.id !== annotationId));

    // Also remove associated field if it exists
    setFields((prev) => prev.filter((field) => field.annotationId !== annotationId));
  }, []);

  const clearAnnotations = useCallback(() => {
    setAnnotations([]);
    setFields([]);
  }, []);

  const startEditing = useCallback((annotation: Annotation) => {
    setEditingAnnotation(annotation);
    setEditComment(annotation.comment || '');
    setEditFieldName(annotation.fieldName || '');
    setEditFieldValue(annotation.fieldValue || '');
  }, []);

  const cancelEditing = useCallback(() => {
    setEditingAnnotation(null);
    setEditComment('');
    setEditFieldName('');
    setEditFieldValue('');
  }, []);

  const saveEdit = useCallback(() => {
    if (editingAnnotation) {
      const updates: Partial<Annotation> = {
        comment: editComment,
        fieldName: editFieldName,
        fieldValue: editFieldValue,
      };

      updateAnnotation(editingAnnotation.id, updates);

      // Update associated field if it exists
      if (editingAnnotation.type === 'field') {
        const associatedField = fields.find((f) => f.annotationId === editingAnnotation.id);
        if (associatedField) {
          updateField(associatedField.id, {
            name: editFieldName,
            value: editFieldValue,
          });
        } else if (editFieldName && editFieldValue) {
          // Create new field if none exists
          addField({
            name: editFieldName,
            value: editFieldValue,
            annotationId: editingAnnotation.id,
            enabled: true,
          });
        }
      }

      setEditingAnnotation(null);
      setEditComment('');
      setEditFieldName('');
      setEditFieldValue('');
    }
  }, [editingAnnotation, editComment, editFieldName, editFieldValue, updateAnnotation, fields, updateField, addField]);

  const createTextSelectionAnnotation = useCallback(
    (selection: {
      pageNumber: number;
      left: number;
      top: number;
      width: number;
      height: number;
      selectedText: string;
    }) => {
      const annotation: Partial<Annotation> = {
        type: 'text',
        pageNumber: selection.pageNumber,
        left: selection.left,
        top: selection.top,
        width: selection.width,
        height: selection.height,
        selectedText: selection.selectedText,
        comment: '',
      };

      setPendingAnnotation(annotation);
      setShowAnnotationPopup(true);
    },
    [],
  );

  const saveTextSelectionAsField = useCallback(
    (fieldName: string, fieldValue: string) => {
      if (pendingAnnotation) {
        const annotation: Omit<Annotation, 'id' | 'createdAt'> = {
          ...pendingAnnotation,
          type: 'field',
          fieldName,
          fieldValue,
          comment: `Field: ${fieldName}`,
        } as Omit<Annotation, 'id' | 'createdAt'>;

        addAnnotation(annotation);
        setShowAnnotationPopup(false);
        setPendingAnnotation(null);
      }
    },
    [pendingAnnotation, addAnnotation],
  );

  const cancelTextSelection = useCallback(() => {
    setShowAnnotationPopup(false);
    setPendingAnnotation(null);
  }, []);

  const getAnnotationsForPage = useCallback(
    (pageNumber: number) => {
      return annotations.filter((ann) => ann.pageNumber === pageNumber);
    },
    [annotations],
  );

  return {
    annotations,
    fields,
    editingAnnotation,
    editComment,
    editFieldName,
    editFieldValue,
    setEditComment,
    setEditFieldName,
    setEditFieldValue,
    showAnnotationPopup,
    pendingAnnotation,
    addAnnotation,
    addField,
    updateField,
    deleteField,
    updateAnnotation,
    deleteAnnotation,
    clearAnnotations,
    startEditing,
    cancelEditing,
    saveEdit,
    createTextSelectionAnnotation,
    saveTextSelectionAsField,
    cancelTextSelection,
    getAnnotationsForPage,
  };
};
