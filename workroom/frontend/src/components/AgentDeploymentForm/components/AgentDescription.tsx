import { AgentDeploymentFormSection } from '../context';
import { InputControlled } from '~/components/form/InputControlled';

export const AgentDescription: AgentDeploymentFormSection = () => {
  return (
    <InputControlled
      fieldName="description"
      aria-label="Agent Description"
      rows={4}
      description="Short description of the agent's purpose and function."
    />
  );
};
