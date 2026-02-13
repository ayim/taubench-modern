import { useState, useEffect, ChangeEvent } from 'react';
import { Input } from '@sema4ai/components';
import { useAgentDetailsContext } from './context';

export const ConversationStarter = () => {
  const { agent, updateAgent } = useAgentDetailsContext();
  const [conversationStarter, setConversationStarter] = useState((agent.extra?.conversation_starter as string) || '');

  useEffect(() => {
    setConversationStarter((agent.extra?.conversation_starter as string) || '');
  }, [agent]);

  const onChange = (e: ChangeEvent<HTMLInputElement>) => setConversationStarter(e.target.value);

  const onBlur = () => {
    updateAgent({ extra: { conversation_starter: conversationStarter } });
  };

  return (
    <Input value={conversationStarter} onBlur={onBlur} onChange={onChange} label="Conversation Starter" rows={3} />
  );
};
