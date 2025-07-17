import { Agent as ASIAgent, Thread as ASIThread } from '@sema4ai/agent-server-interface';
import { components as WorkItemComponents } from '@sema4ai/work-items-interface';

export type Agent = ASIAgent;
export type Thread = ASIThread;

type WorkItemsSchema = WorkItemComponents['schemas'];
export type WorkItem = WorkItemsSchema['WorkItem'];
