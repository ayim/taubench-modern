export type SparUIRoutes = {
  '/conversational/$agentId/$threadId': {
    agentId: string;
    threadId: string;
  };
  '/conversational/$agentId/home': {
    agentId: string;
  };
  '/worker/$agentId': {
    agentId: string;
  };
  '/worker/$agentId/$workItemId': {
    agentId: string;
    workItemId: string;
  };
};
