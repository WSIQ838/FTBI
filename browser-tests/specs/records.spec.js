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

test('student appeal, independent records decision and private outcome', async ({ page }, testInfo) => {
  const student = 'demo-records-' + testInfo.project.name;
  const grounds = 'Synthetic appeal grounds for ' + testInfo.project.name;
  await login(page, student);
  await page.goto('/record/');
  await page.getByRole('link', { name: 'Appeal or view appeal decision', exact: true }).click();
  const appealURL = page.url();
  await page.getByLabel('Reason:', { exact: true }).fill(grounds);
  await accessible(page, testInfo, 'appeal-form-accessibility');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'My withdrawal appeal', exact: true })).toBeVisible();
  await expect(page.getByText(grounds, { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();

  await login(page, 'demo-records-reviewer');
  await page.goto('/registrar/withdrawal-appeals/');
  const row = page.locator('article').filter({ hasText: grounds });
  await row.getByRole('link', { name: 'Review appeal', exact: true }).click();
  await page.getByLabel('Decision:', { exact: true }).selectOption('granted');
  await page.getByLabel('Reason:', { exact: true }).fill('Synthetic grounds accepted: ' + testInfo.project.name);
  await accessible(page, testInfo, 'appeal-review-accessibility');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.locator('article').filter({ hasText: grounds })).toContainText('Granted');
  await page.getByRole('button', { name: 'Sign out' }).click();

  await login(page, student);
  await page.goto('/record/');
  await expect(page.getByText('Withdrawal: Approved', { exact: true })).toBeVisible();
  await page.goto(appealURL);
  await expect(page.getByText('Synthetic grounds accepted: ' + testInfo.project.name, { exact: true })).toBeVisible();
  await accessible(page, testInfo, 'appeal-outcome-accessibility');
  await page.getByRole('button', { name: 'Sign out' }).click();
  await login(page, 'demo-outsider');
  const privateResult = await page.goto(appealURL);
  expect(privateResult.status()).toBe(404);
  await expect(page.getByText(grounds, { exact: true })).toHaveCount(0);
  const staffResult = await page.goto('/registrar/withdrawal-appeals/');
  expect(staffResult.status()).toBe(403);
});
