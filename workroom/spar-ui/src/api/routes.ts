/* eslint-disable @typescript-eslint/ban-types */

export type SparUIRoutes = {
  '/thread/$agentId/$threadId': {
    agentId: string;
    threadId: string;
  };
  '/thread/$agentId/$threadId/chat-details': {
    agentId: string;
    threadId: string;
  };
  '/thread/$agentId/$threadId/data-frames': {
    agentId: string;
    threadId: string;
  };
  '/thread/$agentId/$threadId/evaluations': {
    agentId: string;
    threadId: string;
  };
  '/thread/$agentId/$threadId/files': {
    agentId: string;
    threadId: string;
  };
  '/thread/$agentId': {
    agentId: string;
  };
  '/workItem/$agentId': {
    agentId: string;
  };
  '/workItem/$agentId/create': {
    agentId: string;
  };
  '/workItem/$agentId/$workItemId/$threadId': {
    agentId: string;
    workItemId: string;
    threadId: string;
  };
  '/workItem/$agentId/$workItemId/$threadId/chat-details': {
    agentId: string;
    workItemId: string;
    threadId: string;
  };
  '/workItem/$agentId/$workItemId/$threadId/files': {
    agentId: string;
    workItemId: string;
    threadId: string;
  };
  '/workItem/$agentId/$workItemId/$threadId/workitem-details': {
    agentId: string;
    workItemId: string;
    threadId: string;
  };
  '/workItem/$agentId/$workItemId/$threadId/data-frames': {
    agentId: string;
    workItemId: string;
    threadId: string;
  };
  '/workItem/$agentId/$workItemId': {
    agentId: string;
    workItemId: string;
  };
  '/workItems/list': {};
  '/data-connections': {};
  '/data-connections/create': {};
  '/data-connections/$dataConnectionId': {
    dataConnectionId: string;
  };
  '/home': {};
};

type UnionToIntersection<U> = (U extends unknown ? (x: U) => 0 : never) extends (x: infer I) => 0 ? I : never;
type AllRouteParams = UnionToIntersection<SparUIRoutes[keyof SparUIRoutes]>;
export type LooseRouteParams = { [K in keyof AllRouteParams]?: string };
