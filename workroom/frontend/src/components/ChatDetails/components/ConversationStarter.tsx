import { InputControlled } from '~/components/form/InputControlled';

export const ConversationStarter = () => {
  return <InputControlled fieldName="extra.conversation_starter" label="Conversation Starter" rows={3} />;
};
