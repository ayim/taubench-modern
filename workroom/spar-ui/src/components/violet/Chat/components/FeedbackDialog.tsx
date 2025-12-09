import { Button, Dialog, Input, Form, Box, useSnackbar } from '@sema4ai/components';
import { FC, useCallback } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { useParams } from '../../../../hooks';
import { useSendFeedbackMutation } from '../../../../queries/feedback';

const feedbackFormSchema = z.object({
  feedback: z.string().min(1, 'Feedback is required').max(1000, 'Feedback must be less than 1000 characters'),
});

type FeedbackFormData = z.infer<typeof feedbackFormSchema>;

type Props = {
  open: boolean;
  onClose: () => void;
};

export const FeedbackDialog: FC<Props> = ({ open, onClose }) => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const { addSnackbar } = useSnackbar();

  const form = useForm<FeedbackFormData>({
    resolver: zodResolver(feedbackFormSchema),
    defaultValues: {
      feedback: '',
    },
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
  } = form;

  const { mutate: sendFeedback, isPending: isSubmitting } = useSendFeedbackMutation({ agentId, threadId });

  const handleClose = useCallback(() => {
    onClose();
  }, [onClose]);

  const onSubmit = handleSubmit(({ feedback }) => {
    sendFeedback(
      {
        feedback,
        comment: '', // Keep comment as empty for now
      },
      {
        onSuccess: () => {
          addSnackbar({ message: 'Feedback sent successfully', variant: 'success' });
          handleClose();
        },
        onError: (error: Error) => {
          addSnackbar({ message: error.message, variant: 'danger' });
        },
      },
    );
  });

  return (
    <Dialog size="medium" width="600px" open={open} onClose={handleClose}>
      <Form onSubmit={onSubmit} busy={isSubmitting}>
        <Dialog.Header>
          <Dialog.Header.Title title="Feedback" />
          <Dialog.Header.Description>
            Found an issue or want to give your team feedback on the agent&apos;s response?
          </Dialog.Header.Description>
        </Dialog.Header>
        <Dialog.Content>
          <Box py="$4">
            <Input label="" rows={6} {...register('feedback')} error={errors.feedback?.message} />
          </Box>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="primary" round onClick={onSubmit} loading={isSubmitting} disabled={!isValid}>
            Submit
          </Button>

          <Button variant="secondary" round onClick={handleClose} disabled={isSubmitting}>
            Cancel
          </Button>
        </Dialog.Actions>
      </Form>
    </Dialog>
  );
};
