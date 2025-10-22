# CreateEvalDialog

A reusable dialog component for creating evaluations with form validation.

## Usage

```tsx
import { CreateEvalDialog, type CreateEvalFormData } from '@sema4ai/spar-ui';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from '@sema4ai/components';

function MyComponent() {
  const [isOpen, setIsOpen] = useState(false);
  const queryClient = useQueryClient();
  const { addSnackbar } = useSnackbar();

  const mutation = useMutation({
    mutationFn: async (data: CreateEvalFormData) => {
      const response = await fetch('/api/evals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...data,
          tenantId: 'your-tenant-id',
        }),
      });
      
      if (!response.ok) throw new Error('Failed to create evaluation');
      return response.json();
    },
    onSuccess: () => {
      addSnackbar({ message: 'Evaluation created successfully', variant: 'success' });
      queryClient.invalidateQueries({ queryKey: ['evals'] });
      setIsOpen(false);
    },
    onError: (error) => {
      addSnackbar({ message: error.message, variant: 'error' });
    },
  });

  return (
    <>
      <button onClick={() => setIsOpen(true)}>Create Evaluation</button>
      <CreateEvalDialog
        open={isOpen}
        onClose={() => setIsOpen(false)}
        onSubmit={mutation.mutateAsync}
        isLoading={mutation.isPending}
      />
    </>
  );
}
```

## Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `open` | `boolean` | Yes | Whether the dialog is open |
| `onClose` | `() => void` | Yes | Called when dialog closes |
| `onSubmit` | `(data: CreateEvalFormData) => Promise<void>` | Yes | Called on form submission |
| `isLoading` | `boolean` | No | Shows loading state |

## Types

```tsx
interface CreateEvalFormData {
  name: string;        // Required, max 100 chars
  description: string; // Optional, populated from suggestions when available
  useLiveExecution: boolean; // When true, execute real tools during evaluation
  evaluationCriteria: {
    responseAccuracyExpectation: string; // Required when live actions are enabled
  };
}
```
