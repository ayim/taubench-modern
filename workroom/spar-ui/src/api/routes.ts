export type SparUIRoutes = {
  '/thread/$agentId/$threadId': {
    agentId: string;
    threadId: string;
  };
  '/thread/$agentId': {
    agentId: string;
  };
  '/workItem/$agentId/$workItemId/$threadId': {
    agentId: string;
    workItemId: string;
    threadId: string;
  };
};
