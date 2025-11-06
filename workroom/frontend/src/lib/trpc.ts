import type { SPARRouter as SPARServiceRouter } from '@spar-service';
import { createTRPCReact } from '@trpc/react-query';
import type { inferRouterInputs, inferRouterOutputs } from '@trpc/server';

export type SPARRouter = SPARServiceRouter;
export const trpc = createTRPCReact<SPARRouter>();

export type TrpcInput = inferRouterInputs<SPARRouter>;
export type TrpcOutput = inferRouterOutputs<SPARRouter>;
