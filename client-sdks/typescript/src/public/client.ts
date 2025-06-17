import createClient, { ClientOptions } from 'openapi-fetch';

import type { paths } from './schema.gen';
import { ConversationMonitor, createStream } from './conversation';

type RequireSome<T, K extends keyof T> = Required<Pick<T, K>> & Omit<T, K>;

type StreamPath = '/api/public/v2/agents/{aid}/conversations/{cid}/stream';
type StreamOptions = {
  body: {
    content: string;
  };
  params: {
    path: {
      aid: string;
      cid: string;
    };
  };
};

export const createAgentPublicApiSDK = (
  options: RequireSome<ClientOptions, 'baseUrl'>
) => {
  const httpClient = createClient<paths>(options);

  return {
    ...httpClient,
    stream: (
      _path: StreamPath,
      streamOptions: StreamOptions,
      monitor: ConversationMonitor
    ) => {
      createStream({
        headers: options.headers,
        baseUrl: options.baseUrl,
        path: `/api/public/v2/agents/${streamOptions.params.path.aid}/conversations/${streamOptions.params.path.cid}/stream`,
        monitor,
      }).streamConversation({
        agentId: streamOptions.params.path.aid,
        threadId: streamOptions.params.path.cid,
        initialMessage: streamOptions.body.content,
      });
    },
  };
};
