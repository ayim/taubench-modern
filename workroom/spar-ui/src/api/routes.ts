/* eslint-disable @typescript-eslint/ban-types */

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
  '/data-connections': {};
  '/data-connections/create': {};
  '/data-connections/$dataConnectionId': {
    dataConnectionId: string;
  };
};

type UnionToIntersection<U> = (U extends unknown ? (x: U) => 0 : never) extends (x: infer I) => 0 ? I : never;
type AllRouteParams = UnionToIntersection<SparUIRoutes[keyof SparUIRoutes]>;
export type LooseRouteParams = { [K in keyof AllRouteParams]?: string };
