import { execSync } from 'child_process';
import path from 'path';

async function globalSetup() {
  console.log('Starting test servers...');

  try {
    // Execute the shell script to start servers from the project root
    const scriptPath = path.join(__dirname, 'start-test-servers.sh');
    const projectRoot = path.join(__dirname, '../..');
    execSync(`bash ${scriptPath}`, {
      stdio: 'inherit',
      cwd: projectRoot
    });

    console.log('Test servers started successfully');
  } catch (error) {
    console.error('Failed to start test servers:', error);
    throw error;
  }
}

export default globalSetup;
