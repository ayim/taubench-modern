export const getDataServerConfiguration = (
  params:
    | {
        type: 'ace';
        auth: { username: string; password: string };
      }
    | {
        type: 'studio';
        auth: { username: string; password: string };
        paths: {
          root: string;
          content: string;
          storage: string;
          static: string;
          tmp: string;
          log: string;
          cache: string;
          locks: string;
        };
      },
) => {
  switch (params.type) {
    case 'ace':
      return {
        default_project: 'sema4ai',
        permanent_storage: {
          location: 'local',
        },
        paths: {
          root: '/root/data_storage',
        },
        auth: {
          http_auth_enabled: true,
          http_permanent_session_lifetime: 86400,
          username: params.auth.username,
          password: params.auth.password,
        },
        gui: {
          autoupdate: false,
        },
        debug: false,
        environment: 'local',
        integrations: {},
        api: {
          http: {
            host: '0.0.0.0',
            port: '47334',
            restart_on_failure: true,
            max_restart_count: 3,
            max_restart_interval_seconds: 60,
          },
          mysql: {
            host: '0.0.0.0',
            port: '47335',
            database: 'sema4ai',
            ssl: true,
            restart_on_failure: true,
            max_restart_count: 3,
            max_restart_interval_seconds: 60,
          },
        },
        cache: {
          type: 'local',
        },
        logging: {
          handlers: {
            console: {
              enabled: false,
              level: 'WARNING',
            },
            file: {
              enabled: true,
              level: 'INFO',
              filename: 'data_server.log',
              maxBytes: 1048576,
              backupCount: 5,
            },
          },
        },
        ml_task_queue: {
          type: 'local',
        },
        file_upload_domains: [],
        web_crawling_allowed_sites: [],
      };
    case 'studio':
      return {
        default_project: 'sema4ai',
        permanent_storage: {
          location: 'local',
        },
        paths: params.paths,
        auth: {
          http_auth_enabled: false,
          http_permanent_session_lifetime: 86400,
          username: params.auth.username,
          password: params.auth.password,
        },
        gui: {
          autoupdate: false,
        },
        debug: true,
        environment: 'local',
        integrations: {},
        api: {
          http: {
            host: '127.0.0.1',
            port: '47334',
            restart_on_failure: true,
            max_restart_count: 3,
            max_restart_interval_seconds: 60,
          },
          mysql: {
            host: '127.0.0.1',
            port: '47335',
            database: 'sema4ai',
            ssl: false,
            restart_on_failure: true,
            max_restart_count: 3,
            max_restart_interval_seconds: 60,
          },
        },
        cache: {
          type: 'local',
        },
        logging: {
          handlers: {
            console: {
              enabled: false,
              level: 'WARNING',
            },
            file: {
              enabled: true,
              level: 'INFO',
              filename: 'data_server.log',
              maxBytes: 1048576,
              backupCount: 5,
            },
          },
        },
        ml_task_queue: {
          type: 'local',
        },
        file_upload_domains: [],
        web_crawling_allowed_sites: [],
      };
    default:
      params satisfies never;
      throw Error(`Unsupported type: ${(params as { type: string }).type}`);
  }
};
