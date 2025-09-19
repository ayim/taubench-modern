export type SparUIRoutes = {
  '/thread/$agentId/$threadId': {
    agentId: string;
    threadId: string;
  };
  '/thread/$agentId': {
    agentId: string;
  };
  '/workItem/$agentId/$workItemId': {
    agentId: string;
    workItemId: string;
  };
};
