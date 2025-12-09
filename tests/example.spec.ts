import { test, expect } from '@playwright/test';

test('has dashboard title', async ({ page }) => {
  await page.goto('/');

  // Expect a title "to contain" a substring.
  // The dashboard usually has "Dashboard" in the title or h1.
  // Based on page.tsx: <h1 className="text-3xl font-bold mb-2">Dashboard</h1>
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
});