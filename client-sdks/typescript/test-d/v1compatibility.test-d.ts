import { expectAssignable } from 'tsd';
import { Agent, ActionPackage, Thread } from '../src/private/types';
import type { components as v1 } from '../src/private/v1/schema';

declare const agent: Agent;
expectAssignable<v1['schemas']['Agent']>(agent);

declare const actionPackage: ActionPackage;
expectAssignable<v1['schemas']['ActionPackage']>(actionPackage);

declare const thread: Thread;
expectAssignable<v1['schemas']['Thread']>(thread);
