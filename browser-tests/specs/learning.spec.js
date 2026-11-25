const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

async function login(page, username) {
  await page.goto('/login/');
  await page.getByLabel('Username:').fill(username);
  await page.getByLabel('Password:', { exact: true }).fill(process.env.FTBI_DEMO_PASSWORD);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: /^Welcome,/ })).toBeVisible();
}
async function accessible(page, testInfo, name) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
  await testInfo.attach(name, { body: JSON.stringify(results.violations, null, 2), contentType: 'application/json' });
  expect(results.violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
}

test('keyboard sign-in, student submission, faculty grading and private access', async ({ page }, testInfo) => {
  await page.goto('/login/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();
  await accessible(page, testInfo, 'sign-in-accessibility');
  await login(page, 'demo-' + testInfo.project.name);
  await accessible(page, testInfo, 'dashboard-accessibility');
  await page.getByRole('link', { name: 'Portal preferences', exact: true }).click();
  await page.getByLabel('Timezone:').selectOption('America/Los_Angeles');
  await page.getByLabel('Show courses:').uncheck();
  await accessible(page, testInfo, 'preferences-accessibility');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'My courses', exact: true })).toHaveCount(0);
  await expect(page.getByText(/Times shown in America\/Los_Angeles/)).toBeVisible();
  await page.getByRole('link', { name: 'Portal preferences', exact: true }).click();
  await page.getByLabel('Show courses:').check();
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
  await page.getByRole('link', { name: /DEMO101/ }).click();
  const courseURL = page.url();
  await accessible(page, testInfo, 'course-accessibility');
  await page.getByRole('link', { name: 'Submit or edit work' }).click();
  await page.getByLabel('Body:').fill('A synthetic reflection for ' + testInfo.project.name);
  await accessible(page, testInfo, 'submission-accessibility');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByText('A synthetic reflection for ' + testInfo.project.name)).toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await login(page, 'demo-faculty');
  await page.goto(courseURL);
  const submission = page.locator('article').filter({ hasText: 'A synthetic reflection for ' + testInfo.project.name });
  await submission.getByRole('link', { name: 'Grade submission', exact: true }).click();
  await page.getByLabel('Grade:', { exact: true }).fill('87');
  await page.getByLabel('Feedback:').fill('Demonstration feedback');
  await accessible(page, testInfo, 'grading-accessibility');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await login(page, 'demo-' + testInfo.project.name);
  await page.goto(courseURL);
  await expect(page.getByText('Grade: 87.00', { exact: true })).toBeVisible();
  await expect(page.getByText('Demonstration feedback', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await login(page, 'demo-outsider');
  const response = await page.goto(courseURL);
  expect(response.status()).toBe(404);
  await expect(page.getByText('A synthetic reflection for ' + testInfo.project.name)).toHaveCount(0);
});
