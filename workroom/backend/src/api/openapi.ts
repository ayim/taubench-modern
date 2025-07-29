/**
 * utility types for getting typed routes from OpenAPI specs
 */
export enum Methods {
  get = 'get',
  post = 'post',
  delete = 'delete',
  put = 'put',
  patch = 'patch',
}

export interface Http<Method extends Methods, Path extends string> {
  method: Method;
  path: Path;
  type: `${Method} ${Path}`;
  regex: RegExp;
}
function build<Method extends Methods, Path extends string>(method: Method, path: Path): Http<Method, Path> {
  const pattern = path.replace(/\{(\w+)\}/g, '[^\\/]+');
  const regex = new RegExp(`^${pattern}$`);
  return {
    method,
    path,
    type: `${method} ${path}`,
    regex,
  };
}

type Config = {
  [Method in Methods]?: unknown;
};

interface OpenApi<Paths extends Record<string, Config>> {
  paths: Paths;
}

type GetMethods<T extends Config> = {
  [k in keyof T]: k extends 'get'
    ? Methods.get
    : k extends 'post'
      ? Methods.post
      : k extends 'put'
        ? Methods.put
        : k extends 'patch'
          ? Methods.patch
          : k extends 'delete'
            ? Methods.delete
            : never;
}[keyof T];
type GetHttpRequests<M extends Methods, Path extends string> = {
  [k in M]: Http<k, Path>;
}[M];

export type MakeHttp<Paths extends Record<string, Config>> = {
  [Path in keyof Paths]: Path extends string ? GetHttpRequests<GetMethods<Paths[Path]>, Path> : never;
}[keyof Paths];

export function buildSpec<Paths extends Record<string, Config>>(spec: OpenApi<Paths>) {
  const endpoints = Object.entries(spec.paths)
    .map(([path, config]) => {
      const methods = [];
      if (config.get) {
        methods.push(Methods.get);
      }
      if (config.post) {
        methods.push(Methods.post);
      }
      if (config.put) {
        methods.push(Methods.put);
      }
      if (config.delete) {
        methods.push(Methods.delete);
      }
      if (config.patch) {
        methods.push(Methods.patch);
      }
      return methods.map(
        (method) =>
          build(method, path) as
            | Http<Methods.get, string>
            | Http<Methods.post, string>
            | Http<Methods.put, string>
            | Http<Methods.patch, string>
            | Http<Methods.delete, string>,
      );
    })
    .flat();
  return ({ method, path }: { method: string; path: string }): MakeHttp<Paths> | null => {
    const [pathWithoutQueryParams] = path.split('?');
    const route = endpoints.find(
      (route) => route.method.toLowerCase() === method.toLowerCase() && route.regex.test(pathWithoutQueryParams),
    );

    if (!route) {
      return null;
    }

    return route as MakeHttp<Paths>;
  };
}
