import { Box, Button, Progress, useSnackbar } from '@sema4ai/components';
import { FC, useEffect } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { FormProvider, useForm } from 'react-hook-form';
import { styled } from '@sema4ai/theme';

import { Accordion } from '~/components/Accordion';
import { useAgentQuery, useUpdateAgentMutation } from '~/queries/agents';
import { useFeatureFlag, FeatureFlag } from '~/hooks';

import { AgentDetailsSchema, getDefaultValues } from './components/context';
import { AgentName } from './components/AgentName';
import { AgentVersion } from './components/AgentVersion';
import { ConversationStarter } from './components/ConversationStarter';
import { LLM } from './components/LLM';
import { MCPServers } from './components/MCPServers';
import { Runbook } from './components/Runbook';
import { SemanticData } from './components/SemanticData';

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

export const ChatDetails: FC<{ agentId: string }> = ({ agentId }) => {
  const { addSnackbar } = useSnackbar();
  const { enabled: isAgentDetailsEnabled } = useFeatureFlag(FeatureFlag.agentDetails);
  const { enabled: canConfigureAgents } = useFeatureFlag(FeatureFlag.canConfigureAgents);
  const { mutateAsync: updateAgent, isPending: isUpdatingAgent } = useUpdateAgentMutation({ agentId });
  const { data: agent, isLoading: isAgentLoading } = useAgentQuery({ agentId });

  const agentDetailsForm = useForm<AgentDetailsSchema>({
    resolver: zodResolver(AgentDetailsSchema),
  });

  const {
    formState: { isDirty: isFormChanged },
  } = agentDetailsForm;

  useEffect(() => {
    if (agent) {
      agentDetailsForm.reset(getDefaultValues(agent));
    }
  }, [agent]);

  const onSubmit = agentDetailsForm.handleSubmit(async (data) => {
    await updateAgent(
      { payload: data },
      {
        onSuccess: () => {
          addSnackbar({ message: 'Agent updated successfully', variant: 'success' });
        },
        onError: (error) => {
          addSnackbar({ message: error.message, variant: 'danger' });
        },
      },
    );
  });

  if (!isAgentDetailsEnabled) return null;

  if (isAgentLoading || !agent) {
    return (
      <Box display="flex" height="100%" justifyContent="center" alignItems="center">
        <Progress />
      </Box>
    );
  }

  return (
    <FormProvider {...agentDetailsForm}>
      <Form onSubmit={onSubmit}>
        <Box display="flex" flexDirection="column" gap="$24" p="$8" flex="1">
          <AgentName />
          <Runbook />
          <SemanticData />
          <LLM />
          <MCPServers />
          {canConfigureAgents && (
            <Box>
              <Accordion title="Advanced Options" size="small">
                <Box display="flex" flexDirection="column" gap="$24">
                  <AgentVersion />
                  <ConversationStarter />
                </Box>
              </Accordion>
            </Box>
          )}
        </Box>
        {isFormChanged && (
          <Actions>
            <Button type="submit" loading={isUpdatingAgent} round>
              Update Agent
            </Button>
          </Actions>
        )}
      </Form>
    </FormProvider>
  );
};
