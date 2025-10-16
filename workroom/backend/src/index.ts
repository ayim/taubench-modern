import { createApplication } from './application.js';
import { getConfiguration } from './configuration.js';
import { createMonitoringContext, type MonitoringContext } from './monitoring/index.js';

const gracefulShutdown =
  ({ exit, monitoring, signal }: { exit?: number; monitoring: MonitoringContext; signal?: NodeJS.Signals }) =>
  async () => {
    if (signal) {
      monitoring.logger.info('Shutdown by signal', {
        processSignal: signal,
      });
    }

    process.exit(typeof exit === 'number' ? exit : 0);
  };

const main = async () => {
  const configuration = getConfiguration();
  const monitoring = createMonitoringContext({ logLevel: configuration.logLevel });

  const app = await createApplication({ configuration, monitoring });
  await app.start();

  process.on('warning', (warning) => {
    monitoring.logger.info('Node warning', { error: warning });
  });

  process.on('SIGINT', gracefulShutdown({ monitoring, signal: 'SIGINT' }));
  process.on('SIGTERM', gracefulShutdown({ monitoring, signal: 'SIGTERM' }));
};

main().catch((err) => {
  const monitoring = createMonitoringContext({});
  monitoring.logger.error('Fatal error', { error: err });

  process.exit(1);
});
