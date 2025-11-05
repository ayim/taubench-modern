import { SPARRouter } from '@spar-service';
import { createTRPCReact } from '@trpc/react-query';
import type { inferRouterInputs, inferRouterOutputs } from '@trpc/server';

export const trpc = createTRPCReact<SPARRouter>();

export type TrpcInput = inferRouterInputs<SPARRouter>;
export type TrpcOutput = inferRouterOutputs<SPARRouter>;
