import { FC, useState } from 'react';
import { useParams } from '@tanstack/react-router';
import { Button, Dialog, Grid, Link } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import { AgentPackageInspectionResponse } from '~/queries/agentPackageInspection';
import { IconConversationalAgents, IconWorkerAgents } from '@sema4ai/icons/logos';
import { EXTERNAL_LINKS } from '~/lib/constants';

import { useTenantContext } from '~/lib/tenantContext';
import { AgentUploadForm } from './AgentUploadForm';
import { RouterCardLink } from '~/components/RouterLink';

type Props = {
  setAgentPackageUploadData: (data: {
    agentTemplate: NonNullable<AgentPackageInspectionResponse>;
    agentPackage: File;
  }) => void;
};

export const CreateAgentDialog: FC<Props> = ({ setAgentPackageUploadData }) => {
  const [open, setOpen] = useState(false);
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { features } = useTenantContext();

  if (!features.agentAuthoring.enabled) {
    return null;
  }

  return (
    <>
      <Button icon={IconPlus} round onClick={() => setOpen(true)}>
        Agent
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} width={940}>
        <Dialog.Header>
          <Dialog.Header.Title title="Create new Agent" />
          <Dialog.Header.Description>
            Create a new agent to help you with your tasks.{' '}
            <Link href={EXTERNAL_LINKS.AGENT_DEPLOYMENT_GUIDE} target="_blank">
              Learn more
            </Link>
          </Dialog.Header.Description>
        </Dialog.Header>
        <Dialog.Content>
          <Grid columns={[1, 1, 1, 3]} gap="$24" pt="$4" pb="$32">
            <AgentUploadForm setAgentPackageUploadData={setAgentPackageUploadData} />

            <RouterCardLink
              to="/tenants/$tenantId/agents/new"
              params={{ tenantId }}
              title="Conversational Agent"
              icon={IconConversationalAgents}
              description="Engage in a conversation with your agent."
            />

            <RouterCardLink
              to="/tenants/$tenantId/agents/new"
              search={{ mode: 'worker' }}
              params={{ tenantId }}
              title="Worker Agent"
              icon={IconWorkerAgents}
              description="Automate and manage business processes."
            />
          </Grid>
        </Dialog.Content>
      </Dialog>
    </>
  );
};
