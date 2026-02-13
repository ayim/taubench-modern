/* eslint-disable react/no-array-index-key */
import { FC, useEffect, useRef, useState } from 'react';
import { useForm, FormProvider } from 'react-hook-form';
import { Box, Button, Typography, Progress, useSnackbar, Switch } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { zodResolver } from '@hookform/resolvers/zod';

import { useAgentQuery, useUpdateAgentMutation } from '~/queries/agents';
import { FeatureFlag, useFeatureFlag } from '~/hooks';
import { QuestionGroupFormData } from './components/context';
import { QuestionEdit } from './components/QuestionEdit';
import { QuestionView } from './components/QuestionView';

type Props = {
  agentId: string;
};

const Actions = styled.div`
  position: sticky;
  bottom: 0;
  display: flex;
  gap: ${({ theme }) => theme.space.$8};
  justify-content: flex-start;
  flex-direction: row-reverse;
  background: ${({ theme }) => theme.colors.background.primary.color};
  padding: ${({ theme }) => theme.space.$24};
  margin-top: ${({ theme }) => theme.space.$40};
`;

const Form = styled.form`
  display: flex;
  flex-direction: column;
  position: relative;
  height: 100%;
  overflow-y: auto;
`;

export const ConversationGuides: FC<Props> = ({ agentId }) => {
  const { addSnackbar } = useSnackbar();
  const { enabled: canConfigureAgents } = useFeatureFlag(FeatureFlag.canConfigureAgents);
  const [viewMode, setViewMode] = useState(!canConfigureAgents);
  const questionDragIndex = useRef<number | null>(null);

  const { data: agent, isLoading: isLoadingAgent } = useAgentQuery({
    agentId,
  });
  const { mutateAsync: updateAgentAsync, isPending: isUpdatingAgent } = useUpdateAgentMutation({ agentId });

  const form = useForm<QuestionGroupFormData>({
    resolver: zodResolver(QuestionGroupFormData),
    defaultValues: {
      title: '',
      questions: [],
    },
  });

  useEffect(() => {
    if (agent) {
      form.reset({
        title: agent.question_groups?.[0]?.title ?? '',
        questions: agent.question_groups?.[0]?.questions ?? [],
      });
    }
  }, [agent]);

  const handleAddQuestion = () => {
    form.setValue('questions', [...form.getValues('questions'), ''], { shouldDirty: true });
  };

  const onSubmit = form.handleSubmit(async (data) => {
    if (!agent) return;
    await updateAgentAsync(
      {
        payload: {
          question_groups: [data],
        },
      },
      {
        onSuccess: () => {
          addSnackbar({ message: 'Conversation Guide updated successfully', variant: 'success' });
        },
        onError: (error) => {
          addSnackbar({ message: error.message, variant: 'danger' });
        },
      },
    );
  });

  if (isLoadingAgent) {
    return (
      <Box display="flex" flexDirection="column" gap="$16" padding="$16" height="100%">
        <Box display="flex" alignItems="center" justifyContent="center" flex="1">
          <Progress />
        </Box>
      </Box>
    );
  }

  const questions = form.watch('questions');

  const isFormChanged = form.formState.isDirty;

  return (
    <FormProvider {...form}>
      <Form onSubmit={onSubmit}>
        <Box display="flex" flexDirection="column" gap="$24" p="$8" flex="1">
          <Box display="flex" flexDirection="column" gap="$8">
            <Box display="flex" alignItems="center" gap="$8">
              <Typography fontWeight="bold" mt="$8">
                Conversation Guide
              </Typography>
            </Box>
            <Typography variant="body-medium" color="content.subtle.light">
              Creating a Conversation Guide helps users understand an Agent’s unique capabilities. Edit the
              automatically generated guide based on your Agent below.
            </Typography>
          </Box>

          {canConfigureAgents && (
            <Switch
              aria-label="View Mode"
              value="View Mode"
              checked={viewMode}
              onChange={(event) => setViewMode(event.target.checked)}
            />
          )}
          <Box display="flex" flexDirection="column" gap="$12" flex="1">
            {questions.length === 0 && (
              <Box display="flex" flexDirection="column" gap="$12">
                <Typography variant="body-medium" color="content.subtle.light">
                  No prompts created yet.
                </Typography>
              </Box>
            )}
            {questions.map((question, index) =>
              viewMode ? (
                <QuestionView key={index} question={question} />
              ) : (
                <QuestionEdit key={index} questionIndex={index} questionDragIndex={questionDragIndex} />
              ),
            )}
            {canConfigureAgents && !viewMode && (
              <Box ml="auto">
                <Button variant="ghost" icon={IconPlus} round onClick={handleAddQuestion}>
                  Add Prompt
                </Button>
              </Box>
            )}
          </Box>
        </Box>
        {isFormChanged && (
          <Actions>
            <Button type="submit" loading={isUpdatingAgent} round>
              Save
            </Button>
          </Actions>
        )}
      </Form>
    </FormProvider>
  );
};
