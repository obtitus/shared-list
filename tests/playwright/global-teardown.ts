import { execSync } from 'child_process';
import path from 'path';

async function globalTeardown() {
  console.log('Stopping test servers...');

  try {
    // Execute the shell script to stop servers from the project root
    const scriptPath = path.join(__dirname, 'stop-test-servers.sh');
    const projectRoot = path.join(__dirname, '../..');
    execSync(`bash ${scriptPath}`, {
      stdio: 'inherit',
      cwd: projectRoot
    });

    console.log('Test servers stopped successfully');
  } catch (error) {
    console.error('Failed to stop test servers:', error);
    // Don't throw error here as teardown should not fail tests
  }
}

export default globalTeardown;
