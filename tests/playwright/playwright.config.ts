import { defineConfig, devices } from '@playwright/test';

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// import dotenv from 'dotenv';
// import path from 'path';
// dotenv.config({ path: path.resolve(__dirname, '.env') });

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: '../',
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Allow parallel workers for projects to run in parallel */
  workers: process.env.CI ? 1 : undefined, // Use default workers for local parallel execution
  /* Global setup/teardown for test servers */
  globalSetup: './global-setup.ts',
  globalTeardown: './global-teardown.ts',
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: process.env.CI ? 'json' : 'list',
  /* Stop test execution on first failure */
  maxFailures: 1,
  /* Global test timeout - 5 minutes should be plenty */
  timeout: 5 * 60 * 1000,
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('')`. */
    // baseURL: 'http://localhost:3000',

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',
    /* Reduce timeout for faster feedback */
    actionTimeout: 5000,
    navigationTimeout: 15000,
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      fullyParallel: false, // Tests within chromium run serially
      use: {
        ...devices['Desktop Chrome'],
        baseURL: 'http://localhost:8001',
      },
    },

    {
      name: 'firefox',
      fullyParallel: false, // Tests within firefox run serially
      use: {
        ...devices['Desktop Firefox'],
        baseURL: 'http://localhost:8002',
      },
    },

    {
      name: 'webkit',
      fullyParallel: false, // Tests within webkit run serially
      use: {
        ...devices['Desktop Safari'],
        baseURL: 'http://localhost:8003',
      },
    },

    /* Test against mobile viewports. */
    {
      name: 'Mobile Chrome',
      fullyParallel: false, // Tests within Mobile Chrome run serially
      use: {
        ...devices['Pixel 5'],
        baseURL: 'http://localhost:8004',
      },
    },
    {
      name: 'Mobile Safari',
      fullyParallel: false, // Tests within Mobile Safari run serially
      use: {
        ...devices['iPhone 12'],
        baseURL: 'http://localhost:8005',
      },
    },
    {
      name: 'iPhone SE',
      fullyParallel: false, // Tests within iPhone SE run serially
      use: {
        ...devices['iPhone SE'],
        baseURL: 'http://localhost:8006',
      },
    },
    {
      name: 'iPhone XR',
      fullyParallel: false, // Tests within iPhone XR run serially
      use: {
        ...devices['iPhone XR'],
        baseURL: 'http://localhost:8007',
      },
    },

    /* Test against branded browsers. */
    // {
    //   name: 'Microsoft Edge',
    //   use: { ...devices['Desktop Edge'], channel: 'msedge' },
    // },
    // {
    //   name: 'Google Chrome',
    //   use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    // },
  ],


});
