import { test as setup, expect } from '@playwright/test';
import path from 'path';

const authFile = path.join(__dirname, '../playwright/.auth/user.json');

setup('authenticate', async ({ page }) => {
    const email = process.env.TEST_EMAIL;
    const password = process.env.TEST_PASSWORD;

    if (!email || !password) {
        throw new Error('TEST_EMAIL and TEST_PASSWORD environment variables must be set');
    }

    await page.goto('/api/auth/signin');

    // NextAuth default signin page with Credentials provider
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password').fill(password);

    await page.getByRole('button', { name: 'Sign in with Credentials' }).click();

    // Wait until the page receives the cookies and redirects.
    // Sometimes login flow sets cookies in the process of several redirects.
    // Wait for the final URL to ensure that the cookies are actually set.
    await page.waitForURL('**');

    // Verify we are logged in. The dashboard has "Welcome back" text.
    // The text is "Welcome back, {user.name}!"
    // Use a more flexible locator to find the text
    await expect(page.getByText(/Welcome back/)).toBeVisible();

    await page.context().storageState({ path: authFile });
});
