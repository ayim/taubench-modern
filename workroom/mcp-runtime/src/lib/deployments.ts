import type { AsyncResult } from '@sema4ai/shared-utils';
import { exec, spawn, type ChildProcess } from 'node:child_process';
import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import unzipper from 'unzipper';
import { parse as parseYaml } from 'yaml';
import z from 'zod';
import type { Configuration } from '../configuration.ts';
import type { Deployment } from '../types.ts';
import { Mutex } from '../util/mutex.ts';
import type { DatabaseClient } from './database.ts';

// How long to delay the reboot of an Action Server process in case it stops unexpectedly
const ACTION_SERVER_REBOOT_DELAY_IN_MS = 5000;

// Timeout / interval for polling for Action Server responsiveness
const ACTION_SERVER_RESPONSIVENESS_TIMEOUT_IN_MS = 30_000;
const ACTION_SERVER_RESPONSIVENESS_POLL_INTERVAL_IN_MS = 1000;

type AgentSpecActionPackages = z.infer<typeof AgentSpecActionPackages>;
const AgentSpecActionPackages = z.object({
  'agent-package': z.object({
    agents: z.array(
      z.object({
        'action-packages': z.array(
          z.object({
            whitelist: z.string(),
            path: z.string(),
          }),
        ),
      }),
    ),
  }),
});

export const getDeploymentUrl = ({
  configuration,
  deploymentId,
}: {
  configuration: Pick<Configuration, 'serverHttpUrl' | 'httpApiPort'>;
  deploymentId: string;
}): string => {
  const deploymentUrl = new URL(configuration.serverHttpUrl);
  deploymentUrl.port = configuration.httpApiPort.toString();
  deploymentUrl.pathname = `/deployments/${deploymentId}/mcp/`;
  return deploymentUrl.href;
};

const execAsync = (cmd: string) => {
  return new Promise<string>((resolve, reject) => {
    exec(cmd, (error, stdout, stderr) => {
      if (error) {
        console.error(stderr);
        return reject(`Process exited with code ${error.code ?? 'UNKNOWN'}`);
      }
      return resolve(stdout);
    });
  });
};

const extractAgentPackage = async ({
  agentPackageZipPath,
  agentOutputDir,
}: {
  agentPackageZipPath: string;
  agentOutputDir: string;
}): AsyncResult<void> => {
  try {
    const zip = await unzipper.Open.file(agentPackageZipPath);
    await zip.extract({ path: agentOutputDir });
    return {
      success: true,
      data: undefined,
    };
  } catch (error) {
    console.error(`Failed to extract Agent Package from ${agentPackageZipPath} to ${agentOutputDir}`);
    return {
      success: false,
      error: {
        code: 'failed_to_extract_agent_package',
        message: 'Failed to extract Agent Package',
      },
    };
  }
};

const getActionPackages = async ({
  agentPackagePath,
}: {
  agentPackagePath: string;
}): AsyncResult<{ actionPackages: { whitelist: string; path: string }[] }> => {
  const agentSpecContents: unknown = await (async () => {
    try {
      return parseYaml(
        await readFile(join(agentPackagePath, 'agent-spec.yaml'), {
          encoding: 'utf-8',
        }),
      );
    } catch (error) {
      console.error('Failed to read agent-spec.yaml', (error as Error).message);
      return null;
    }
  })();
  if (agentSpecContents === null) {
    return {
      success: false,
      error: {
        code: 'failed_to_read_agent_spec',
        message: 'Failed to read Agent spec',
      },
    };
  }

  const agentSpecParseResult = AgentSpecActionPackages.safeParse(agentSpecContents);
  if (!agentSpecParseResult.success) {
    console.error('Failed to parse agent-spec.yaml', agentSpecParseResult.error.message);
    return {
      success: false,
      error: {
        code: 'failed_to_parse_agent_spec',
        message: 'Failed to parse agent-spec.yaml',
      },
    };
  }

  const agentSpec = agentSpecParseResult.data;
  const actionPackages = agentSpec['agent-package'].agents[0]['action-packages'];

  return {
    success: true,
    data: { actionPackages },
  };
};

const importActionPackages = async ({
  actionPackages,
  agentPackagePath,
  actionServerDataDir,
  deploymentId,
}: {
  actionPackages: { whitelist: string; path: string }[];
  agentPackagePath: string;
  actionServerDataDir: string;
  deploymentId: string;
}): AsyncResult<void> => {
  for (const actionPackage of actionPackages) {
    const { path, whitelist } = actionPackage;
    try {
      const actionPackageZipPath = join(agentPackagePath, 'actions', path);
      const actionPackageDir = dirname(actionPackageZipPath);
      console.log(`[${deploymentId}] Extracting Action Package: ${actionPackageZipPath}`);
      const actionPackageZip = await unzipper.Open.file(actionPackageZipPath);
      await actionPackageZip.extract({ path: actionPackageDir });
      await rm(actionPackageZipPath);

      console.log(`[${deploymentId}] Importing Action Package to Action Server`);
      await execAsync(
        `action-server import --verbose --dir="${actionPackageDir}" --datadir="${actionServerDataDir}" --whitelist="${whitelist}"`,
      );
    } catch (error) {
      console.error('Failed to import Action Package', (error as Error).message);
      return {
        success: false,
        error: {
          code: 'failed_to_import_action_package',
          message: 'Failed to import Action Package',
        },
      };
    }
  }

  return {
    success: true,
    data: undefined,
  };
};

export const createActionDeployer = (ctx: { configuration: Configuration; db: DatabaseClient }) => {
  const { configuration, db } = ctx;

  const rccMutex = new Mutex();
  const serverProcessMap = new Map<string, ChildProcess>();

  const getDeploymentDir = async ({ deploymentId }: { deploymentId: string }) => {
    const deploymentDir = join(configuration.persistentDataDirectory, 'deployments', deploymentId);
    await mkdir(deploymentDir, { recursive: true });
    return deploymentDir;
  };

  const getAgentPackageExtractDir = async ({ deploymentId }: { deploymentId: string }) => {
    const deploymentDir = await getDeploymentDir({ deploymentId });
    const agentPackageExtractDir = join(deploymentDir, 'agent');
    await mkdir(agentPackageExtractDir, { recursive: true });
    return agentPackageExtractDir;
  };

  const getActionServerDataDir = async ({ deploymentId }: { deploymentId: string }) => {
    const actionServerDataDir = join(homedir(), 'as-runtime-data', deploymentId);
    await mkdir(actionServerDataDir, { recursive: true });
    return actionServerDataDir;
  };

  const getAgentZipPath = async ({ deploymentId }: { deploymentId: string }) => {
    const deploymentDir = await getDeploymentDir({ deploymentId });
    return join(deploymentDir, 'agent.zip');
  };

  const prepareEnvironment = async ({
    deploymentId,
    agentPackageZipPath,
  }: {
    deploymentId: string;
    agentPackageZipPath: string;
  }): AsyncResult<{
    actionServerDataDir: string;
  }> => {
    console.log(`[${deploymentId}] Preparing environment for ${deploymentId}`);

    await rccMutex.lock();

    try {
      const agentOutputDir = await getAgentPackageExtractDir({ deploymentId });

      const extractAgentPackageResult = await extractAgentPackage({ agentPackageZipPath, agentOutputDir });
      if (!extractAgentPackageResult.success) {
        return extractAgentPackageResult;
      }

      const getActionPackagesResult = await getActionPackages({ agentPackagePath: agentOutputDir });
      if (!getActionPackagesResult.success) {
        return getActionPackagesResult;
      }
      const { actionPackages } = getActionPackagesResult.data;

      const actionServerDataDir = await getActionServerDataDir({ deploymentId });
      const importActionPackagesResult = await importActionPackages({
        actionPackages,
        agentPackagePath: agentOutputDir,
        actionServerDataDir,
        deploymentId,
      });
      if (!importActionPackagesResult.success) {
        return importActionPackagesResult;
      }

      console.log(`Done preparing environment for ${deploymentId}`);

      return {
        success: true,
        data: {
          actionServerDataDir,
        },
      };
    } finally {
      rccMutex.unlock();
    }
  };

  const runServer = async ({
    deploymentId,
    port,
    waitForServer = false,
  }: {
    deploymentId: string;
    port: number;
    waitForServer?: boolean;
  }): Promise<{ port: number }> => {
    const serverUrl = getDeploymentUrl({ configuration, deploymentId });

    const actionServerDataDir = await getActionServerDataDir({ deploymentId });
    const isEmpty = (await readdir(actionServerDataDir)).length === 0;

    if (isEmpty) {
      console.log(`[${deploymentId}] Action Server runtime data directory is empty, preparing environment`);
      await prepareEnvironment({ deploymentId, agentPackageZipPath: await getAgentZipPath({ deploymentId }) });
    } else {
      console.log(
        `[${deploymentId}] Action Server runtime data directory is not empty, skipping environment preparation`,
      );
    }

    const actionServer = spawn(
      '/usr/local/bin/action-server',
      [
        'start',
        `--server-url=${serverUrl}`,
        '--address',
        '127.0.0.1',
        '--port',
        port.toString(),
        '--verbose',
        `--datadir=${actionServerDataDir}`,
        '--actions-sync=false',
        '--reuse-processes',
        '--min-processes=2',
        '--max-processes=4',
        '--kill-lock-holder',
      ],
      {
        detached: true, // Required to kill the server and its (uvicorn) child processes
        killSignal: 'SIGKILL',
        env: {
          ...process.env,
          SEMA4AI_SKIP_UPDATE_CHECK: '1',
        }, // TODO: *Selectively* pass environment
      },
    );
    serverProcessMap.set(deploymentId, actionServer);

    actionServer.stdout.setEncoding('utf-8');
    actionServer.stderr.setEncoding('utf-8');
    actionServer.stdout.on('data', (data: string) => {
      data.split('\n').forEach((line: string) => {
        console.log(`[${deploymentId}] ${line.trimEnd()}`);
      });
    });
    actionServer.stderr.on('data', (data: string) => {
      data.split('\n').forEach((line: string) => {
        console.log(`[${deploymentId}] ${line.trimEnd()}`);
      });
    });

    actionServer.on('close', () => {
      console.log(
        `Action Server for deployment ${deploymentId} stopped unexpectedly. Will restart the server in ${ACTION_SERVER_REBOOT_DELAY_IN_MS} ms`,
      );
      setTimeout(() => {
        runServer({ deploymentId, port });
      }, ACTION_SERVER_REBOOT_DELAY_IN_MS);
    });

    actionServer.on('error', (err) => {
      console.log(`[${deploymentId}] ERROR:`, err);
    });

    return new Promise((resolve, reject) => {
      if (!waitForServer) {
        return resolve({ port });
      }

      const startTime = Date.now();

      const checkServerResponsive = async () => {
        try {
          const internalUrl = `http://127.0.0.1:${port}/openapi.json`;
          const response = await fetch(internalUrl, {
            method: 'GET',
            signal: AbortSignal.timeout(500),
          });

          if (response.ok) {
            clearInterval(serverPollIntervalId);
            return resolve({ port });
          }
        } catch (err) {
          // Server not ready yet, continue polling
        }

        if (Date.now() - startTime > ACTION_SERVER_RESPONSIVENESS_TIMEOUT_IN_MS) {
          clearInterval(serverPollIntervalId);
          reject(new Error(`Server failed to start within ${ACTION_SERVER_RESPONSIVENESS_TIMEOUT_IN_MS}ms`));
        }
      };

      const serverPollIntervalId = setInterval(checkServerResponsive, ACTION_SERVER_RESPONSIVENESS_POLL_INTERVAL_IN_MS);
    });
  };

  const createDeployment = async ({
    deploymentId,
    agentPackageZip,
  }: {
    deploymentId: string;
    agentPackageZip: Buffer;
  }): AsyncResult<Deployment> => {
    const listDeploymentsResult = await db.listDeployments();
    if (!listDeploymentsResult.success) {
      return listDeploymentsResult;
    }
    const deployments = listDeploymentsResult.data;

    const currentDeploymentCount = deployments.length;
    if (currentDeploymentCount >= configuration.maxServerCount) {
      return {
        success: false,
        error: {
          code: 'server_at_capacity',
          message: `Server is at capacity - already running ${configuration.maxServerCount} Action Servers`,
        },
      };
    }

    const deploymentExists = deployments.some((deployment) => deployment.id === deploymentId);
    if (deploymentExists) {
      return {
        success: false,
        error: {
          code: 'deployment_exists',
          message: `Deployment ${deploymentId} already exists`,
        },
      };
    }

    const getAvailablePortResult = await db.getAvailablePort();
    if (!getAvailablePortResult.success) {
      return getAvailablePortResult;
    }

    const serverPort = getAvailablePortResult.data;
    if (serverPort === null) {
      return {
        success: false,
        error: {
          code: 'failed_to_assign_port',
          message: 'Failed to assign port to Action Server',
        },
      };
    }

    const createDeploymentResult = await db.createDeployment({
      id: deploymentId,
      port: serverPort,
    });
    if (!createDeploymentResult.success) {
      return createDeploymentResult;
    }
    const deployment = createDeploymentResult.data;

    const startDeployment = async () => {
      const agentPackageZipPath = await getAgentZipPath({ deploymentId });

      try {
        await writeFile(agentPackageZipPath, agentPackageZip);
      } catch (error) {
        console.error(`Failed to write file to ${agentPackageZipPath}`);
        const updateDeploymentResult = await db.updateDeployment({
          id: deployment.id,
          status: 'build_failed',
        });
        if (!updateDeploymentResult.success) {
          console.error(`Failed to update deployment ${deployment.id}`);
        }
        return;
      }

      const updateDeploymentResult = await db.updateDeployment({
        id: deployment.id,
        status: 'building',
        zip_path: agentPackageZipPath,
      });
      if (!updateDeploymentResult.success) {
        console.error(`Failed to update deployment ${deployment.id}`);
        return;
      }

      const environmentResult = await prepareEnvironment({ deploymentId, agentPackageZipPath });
      if (!environmentResult.success) {
        const updateDeploymentResult = await db.updateDeployment({
          id: deployment.id,
          status: 'build_failed',
        });
        if (!updateDeploymentResult.success) {
          console.error(`Failed to update deployment ${deployment.id}`);
        }
        return;
      }

      await runServer({
        deploymentId: deployment.id,
        port: serverPort,
      });

      const updateDeploymentRunningResult = await db.updateDeployment({
        id: deployment.id,
        status: 'running',
        zip_path: agentPackageZipPath,
      });
      if (!updateDeploymentRunningResult.success) {
        console.error(`Failed to update deployment ${deployment.id}`);
      }
    };

    startDeployment();

    return {
      success: true,
      data: deployment,
    };
  };

  const stopServer = async ({ deploymentId }: { deploymentId: string }): AsyncResult<{ deploymentId: string }> => {
    console.log(`Stopping server for deployment ${deploymentId}`);

    const serverProcess = serverProcessMap.get(deploymentId);
    if (!serverProcess) {
      console.log(`No server found for deployment ${deploymentId}, not stopping`);
      return {
        success: true,
        data: {
          deploymentId,
        },
      };
    }

    if (serverProcess.exitCode !== null) {
      console.log(`Server for deployment ${deploymentId} already stopped`);
      return {
        success: true,
        data: {
          deploymentId,
        },
      };
    }

    // Remove the server's "close" listener to disable automatic reboots
    serverProcess.removeAllListeners('close');

    const success = serverProcess.kill('SIGINT'); // Kill the action-server process
    if (success && serverProcess.pid) {
      process.kill(-serverProcess.pid); // Kill the process *group* (uvicorn child processes)
    } else {
      return {
        success: false,
        error: {
          code: 'failed_to_kill_action_server',
          message: `Failed to kill Action Server for deployment ${deploymentId}`,
        },
      };
    }

    serverProcessMap.delete(deploymentId);

    return {
      success: true,
      data: {
        deploymentId,
      },
    };
  };

  const destroyDeployment = async ({
    deploymentId,
  }: {
    deploymentId: string;
  }): AsyncResult<{ deploymentId: string }> => {
    const deleteDeploymentResult = await ctx.db.deleteDeployment({ id: deploymentId });
    if (!deleteDeploymentResult.success) {
      return deleteDeploymentResult;
    }

    const stopServerResult = await stopServer({ deploymentId });
    if (!stopServerResult.success) {
      return stopServerResult;
    }

    const deploymentDir = await getDeploymentDir({ deploymentId });
    try {
      await rm(deploymentDir, {
        recursive: true,
        force: true,
      });
    } catch (err) {
      return {
        success: false,
        error: {
          code: 'failed_to_delete_deployment_data',
          message: `Failed to destroy deployment ${deploymentId} - removing deployment data failed`,
        },
      };
    }

    const actionServerDataDir = await getActionServerDataDir({ deploymentId });
    try {
      await rm(actionServerDataDir, {
        recursive: true,
        force: true,
      });
    } catch (err) {
      return {
        success: false,
        error: {
          code: 'failed_to_delete_action_server_data',
          message: `Failed to destroy deployment ${deploymentId} - removing action serverdata failed`,
        },
      };
    }

    return {
      success: true,
      data: {
        deploymentId,
      },
    };
  };

  const rehydrateDeployments = async () => {
    const listDeploymentsResult = await db.listDeployments();
    if (!listDeploymentsResult.success) {
      return listDeploymentsResult;
    }
    const deployments = listDeploymentsResult.data;

    for (const deployment of deployments) {
      if (deployment.port === null) {
        console.warn(`Deployment ${deployment.id} has no port defined - not rehydrating`);
        continue;
      }
      console.log(`Rehydrating deployment ${deployment.id}`);
      try {
        await runServer({
          deploymentId: deployment.id,
          port: deployment.port,
          waitForServer: true,
        });
      } catch (error) {
        console.error(`Failed to rehydrate deployment ${deployment.id}`, error);
        // TODO: Delete this deployment?
        continue;
      }
    }
  };

  return {
    createDeployment,
    destroyDeployment,
    rehydrateDeployments,
  };
};
