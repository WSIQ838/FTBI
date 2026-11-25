const { defineConfig, devices } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './specs', fullyParallel: false, workers: 1, retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:8765', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    { name: 'mobile', use: { ...devices['iPhone 13'] } },
    { name: 'dark', use: { ...devices['Desktop Chrome'], colorScheme: 'dark' } },
  ],
  webServer: {
    command: `"${process.env.FTBI_PYTHON || 'python'}" ../manage.py runserver 127.0.0.1:8765 --noreload --settings=ftbi.browser_settings`,
    url: 'http://127.0.0.1:8765/login/', reuseExistingServer: process.env.FTBI_EXTERNAL_TEST_SERVER === '1' && !process.env.CI,
    env: { DJANGO_DEBUG: '1', FTBI_BROWSER_TESTING: '1' }, timeout: 30000,
  },
});
