import { Agent as ASIAgent, Thread as ASIThread } from '@sema4ai/agent-server-interface';
import { components } from '@sema4ai/work-items-interface';

export type Agent = ASIAgent;
export type Thread = ASIThread;
export type WorkItem = components['schemas']['WorkItem'] & {
  work_item_id: string;
  work_item_url?: string;
  created_at?: string;
};
