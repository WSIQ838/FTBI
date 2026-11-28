const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const origin = 'http://localhost:8765';

async function login(page) {
  await page.goto(origin + '/login/');
  await page.getByLabel('Username:').fill('demo-passkey');
  await page.getByLabel('Password:', { exact: true }).fill(process.env.FTBI_DEMO_PASSWORD);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
}

test('passkey enrollment, required verification and revocation with a virtual authenticator', async ({ page, context }) => {
  const cdp = await context.newCDPSession(page);
  await cdp.send('WebAuthn.enable');
  const { authenticatorId } = await cdp.send('WebAuthn.addVirtualAuthenticator', { options: {
    protocol: 'ctap2', transport: 'internal', hasResidentKey: true, hasUserVerification: true,
    isUserVerified: true, automaticPresenceSimulation: true,
  }});
  try {
    await login(page);
    await expect(page.getByRole('heading', { name: /^Welcome,/ })).toBeVisible();
    await page.goto(origin + '/account/passkeys/');
    await page.getByLabel('Passkey name', { exact: true }).fill('Synthetic browser passkey');
    await page.getByLabel('Password confirmation', { exact: true }).fill(process.env.FTBI_DEMO_PASSWORD);
    expect((await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze()).violations).toEqual([]);
    await page.getByRole('button', { name: 'Add passkey', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Synthetic browser passkey', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Sign out' }).click();
    await login(page);
    await expect(page.getByRole('button', { name: 'Verify passkey', exact: true })).toBeVisible();
    await page.goto(origin + '/');
    await expect(page.getByRole('button', { name: 'Verify passkey', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Verify passkey', exact: true }).click();
    await expect(page.getByRole('heading', { name: /^Welcome,/ })).toBeVisible();
    await page.goto(origin + '/account/passkeys/');
    await page.getByLabel('Password to revoke Synthetic browser passkey', { exact: true }).fill(process.env.FTBI_DEMO_PASSWORD);
    await page.getByRole('button', { name: 'Revoke Synthetic browser passkey', exact: true }).click();
    await expect(page.getByText('No passkeys registered.', { exact: true })).toBeVisible();
  } finally { await cdp.send('WebAuthn.removeVirtualAuthenticator', { authenticatorId }); }
});
