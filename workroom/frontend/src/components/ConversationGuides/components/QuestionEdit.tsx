/* eslint-disable no-param-reassign */
import type { DragEvent, FC, RefObject } from 'react';
import { Box, Button } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { IconDots, IconTrash } from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';

import { InputControlled } from '~/components/form/InputControlled';
import { QuestionGroupFormData } from './context';

const Draggable = styled(Button)`
  cursor: grab;
`;

type Props = {
  questionIndex: number;
  questionDragIndex: RefObject<number | null>;
};

export const QuestionEdit: FC<Props> = ({ questionIndex, questionDragIndex }) => {
  const form = useFormContext<QuestionGroupFormData>();

  const handleDragStart = (event: DragEvent<HTMLDivElement>) => {
    const { dataTransfer } = event;
    if (!dataTransfer) {
      return;
    }
    dataTransfer.effectAllowed = 'move';
    questionDragIndex.current = questionIndex;
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const { dataTransfer } = event;
    if (!dataTransfer) {
      return;
    }
    dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (questionDragIndex.current === null || questionDragIndex.current === questionIndex) {
      return;
    }

    const updatedQuestions = [...form.getValues('questions')];
    const [movedQuestion] = updatedQuestions.splice(questionDragIndex.current, 1);
    updatedQuestions.splice(questionIndex, 0, movedQuestion);

    form.setValue('questions', updatedQuestions, { shouldDirty: true });
    questionDragIndex.current = null;
  };

  const handleDragEnd = () => {
    questionDragIndex.current = null;
  };

  const handleDeleteQuestion = () => {
    form.setValue(
      'questions',
      form.getValues('questions').filter((_, i) => i !== questionIndex),
      { shouldDirty: true },
    );
  };

  const question = form.watch(`questions.${questionIndex}`);

  return (
    <Box
      display="flex"
      gap="$8"
      draggable
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onDragEnd={handleDragEnd}
    >
      <Draggable variant="ghost" round icon={IconDots} aria-label="Reorder Questions" />
      <Box flex="1">
        <InputControlled
          fieldName={`questions.${questionIndex}`}
          aria-label="Prompt"
          errorMessage={form.formState.errors.questions?.[questionIndex]?.message}
          autoFocus={question === ''}
        />
      </Box>
      <Button variant="ghost" round icon={IconTrash} aria-label="Delete Question" onClick={handleDeleteQuestion} />
    </Box>
  );
};
