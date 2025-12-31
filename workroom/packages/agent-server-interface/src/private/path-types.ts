/**
 * Type helpers for extracting request/response types from OpenAPI paths.
 * These are generic utilities that work with the generated `paths` type.
 */
import type { paths } from './schema.gen';

type HttpMethod =
  | 'get'
  | 'put'
  | 'post'
  | 'delete'
  | 'options'
  | 'head'
  | 'patch'
  | 'trace';

type HasMethodForPath<T, K extends keyof T> = K extends keyof T
  ? Pick<T, K> extends Required<Pick<T, K>>
    ? true
    : false
  : false;

type RoutesForMethod<M extends HttpMethod> = {
  [R in keyof paths]: HasMethodForPath<paths[R], M> extends true ? R : never;
}[keyof paths];

/**
 * Extracts the response body type for a given HTTP method and API route.
 *
 * @example
 * type AgentResponse = ServerResponse<'get', '/api/v1/agents/{agent_id}'>;
 */
export type ServerResponse<
  TMethod extends HttpMethod,
  TAPIRoute extends RoutesForMethod<TMethod> = never,
> = paths[TAPIRoute][TMethod] extends {
  responses: { 200: { content: { 'application/json': unknown } } };
}
  ? paths[TAPIRoute][TMethod]['responses'][200]['content']['application/json']
  : never;

/**
 * Extracts the request body, query params, or path params for a given HTTP method and API route.
 *
 * @example
 * type CreateAgentBody = ServerRequest<'post', '/api/v1/agents/', 'requestBody'>;
 * type AgentPathParams = ServerRequest<'get', '/api/v1/agents/{agent_id}', 'path'>;
 * type ListAgentsQuery = ServerRequest<'get', '/api/v1/agents/', 'query'>;
 */
export type ServerRequest<
  TMethod extends HttpMethod,
  TAPIRoute extends RoutesForMethod<TMethod> = never,
  TArg extends 'requestBody' | 'query' | 'path' = never,
> = TArg extends keyof paths[TAPIRoute][TMethod]
  ? paths[TAPIRoute][TMethod][TArg] extends {
      content: { 'application/json': infer Body };
    }
    ? Body
    : never
  : TArg extends 'path'
    ? 'parameters' extends keyof paths[TAPIRoute][TMethod]
      ? paths[TAPIRoute][TMethod]['parameters'] extends { path?: infer Path }
        ? Path
        : never
      : never
    : TArg extends 'query'
      ? 'parameters' extends keyof paths[TAPIRoute][TMethod]
        ? paths[TAPIRoute][TMethod]['parameters'] extends {
            query?: infer Query;
          }
          ? Query
          : never
        : never
      : never;
