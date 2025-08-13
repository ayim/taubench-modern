/*
 * This script is used to run the tests for the sai-sdk package.
 * It will install the dependencies, start the agent server in the background,
 * wait for the agent server to be fully ready, and then run the tests.
 * It will also clean up the agent server process after the tests are run.
 *
 * It is used in the GitHub Actions workflow to run the tests for the sai-sdk package.
 *
 * It can be used in the local development environment.
 */

const { spawn, exec } = require('child_process');
const { promisify } = require('util');
const execAsync = promisify(exec);

function goToProjectRoot() {
  const path = require('path');
  const process = require('process');
  const rootDir = path.resolve(__dirname, '../..');
  process.chdir(rootDir);
  console.log(`>>> Changed directory to ${rootDir}`);
  return rootDir;
}

// Run make sync to install the dependencies
const installDependencies = async () => {
  goToProjectRoot();
  console.log('>>> Installing dependencies with make sync...');
  try {
    const { stdout, stderr } = await execAsync('make sync');
    console.log('>>> Dependencies installed successfully');
    if (stdout) console.log(`>>> Stdout: ${stdout}`);
    if (stderr) console.log(`>>> Stderr: ${stderr}`);
  } catch (error) {
    console.error(`!!! Error installing dependencies: ${error.message}`);
    throw error;
  }
};

// Run make run-as-studio in the background
function runAgentServerInBackground() {
  return new Promise((resolve, reject) => {
    goToProjectRoot();
    console.log('>>> Starting Agent Server in background...');

    const serverProcess = spawn('make', ['run-as-studio'], {
      detached: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    // Store the process ID for cleanup
    global.serverPid = serverProcess.pid;

    let hasStarted = false;
    let startupTimeout;

    serverProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log(`>>> Agent Server stdout: ${output}`);

      // Look for signs that the server has started
      if (
        !hasStarted &&
        (output.includes('Server started') || output.includes('listening') || output.includes('ready'))
      ) {
        hasStarted = true;
        if (startupTimeout) clearTimeout(startupTimeout);
        console.log('>>> Agent Server appears to be ready');
        resolve(serverProcess);
      }
    });

    serverProcess.stderr.on('data', (data) => {
      console.log(`>>> Agent Server stderr: ${data.toString()}`);
    });

    serverProcess.on('error', (error) => {
      console.error(`!!! Agent Server process error: ${error.message}`);
      if (!hasStarted) reject(error);
    });

    serverProcess.on('exit', (code, signal) => {
      console.log(`>>> Agent Server process exited with code ${code}, signal ${signal}`);
      if (!hasStarted && code !== 0) {
        reject(new Error(`Agent Server failed to start, exit code: ${code}`));
      }
    });

    // Give the server some time to start, then assume it's ready
    startupTimeout = setTimeout(() => {
      if (!hasStarted) {
        console.log('>>> Assuming Agent Server is ready after timeout');
        hasStarted = true;
        resolve(serverProcess);
      }
    }, 10000); // 10 second timeout
  });
}

// Run npm run test
async function runTests() {
  goToProjectRoot();
  console.log('>>> Running tests...');
  try {
    // Change to the sai-sdk directory for tests
    const path = require('path');
    process.chdir(path.join(process.cwd(), 'packages', 'typescript-sai-sdk'));

    const { stdout, stderr } = await execAsync('npm run test');
    console.log('>>> Tests completed successfully');
    if (stdout) console.log(`>>> Test stdout: ${stdout}`);
    if (stderr) console.log(`>>> Test stderr: ${stderr}`);
    return true;
  } catch (error) {
    console.error(`!!! Test error: ${error.message}`);
    throw error;
  }
}

// Kill the Agent Server process
async function killAgentServer() {
  console.log('>>> Cleaning up agent server...');
  try {
    if (global.serverPid) {
      // Try to kill the specific process first
      await execAsync(`kill ${global.serverPid}`);
      console.log(`>>> Killed server process ${global.serverPid}`);
    }

    // Also try to kill any remaining processes
    await execAsync('pkill -f "make run-as-studio"');
    console.log('>>> Cleaned up any remaining agent server processes');
  } catch (error) {
    // It's okay if the process is already dead
    console.log('>>> Cleanup completed (some processes may have already exited)');
  }
}

// Main execution
async function main() {
  try {
    // Step 1: Install dependencies
    await installDependencies();

    // Step 2: Start agent server in background
    await runAgentServerInBackground();

    // Step 3: Wait a bit more for server to be fully ready
    console.log('>>> Waiting 5 seconds for Agent Server to be fully ready...');
    await new Promise((resolve) => setTimeout(resolve, 5000));

    // Step 4: Run tests
    await runTests();

    console.log('>>> All operations completed successfully!');
  } catch (error) {
    console.error(`!!! Main execution error: ${error.message}`);
    process.exitCode = 1;
  } finally {
    // Step 5: Always cleanup
    await killAgentServer();
    console.log('>>> Script finished');
  }
}

// Handle process termination gracefully
process.on('SIGINT', async () => {
  console.log('>>> Received SIGINT, cleaning up...');
  await killAgentServer();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('>>> Received SIGTERM, cleaning up...');
  await killAgentServer();
  process.exit(0);
});

main();
