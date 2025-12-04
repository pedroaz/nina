---
description: Verify project health after changes
---

# Verification Workflow

This workflow verifies that all packages build successfully, pass linting, and tests pass after making changes.

## Quick Verification Command

Run this single command to verify everything:

```bash
// turbo
pnpm --filter web-app build && pnpm --filter landing-page build && pnpm --filter web-app lint && pnpm --filter landing-page lint && pnpm test:e2e
```

## Step-by-Step Verification

If you prefer to run each step separately:

### 1. Build Verification

Build both packages to ensure there are no compilation errors:

```bash
// turbo
pnpm --filter web-app build
```

```bash
// turbo
pnpm --filter landing-page build
```

### 2. Lint Verification

Check code quality and style:

```bash
// turbo
pnpm --filter web-app lint
```

```bash
// turbo
pnpm --filter landing-page lint
```

### 3. Test Verification

Run E2E tests (optimized for speed - runs only chromium):

```bash
// turbo
pnpm test:e2e
```

## Expected Results

✅ **All builds should complete successfully** with no errors
✅ **All linting should pass** with no errors
✅ **All tests should pass**

## Notes

- The E2E tests are configured to run only on Chromium for speed
- To run tests on all browsers (chromium, firefox, webkit), uncomment the browser configs in `playwright.config.ts`
- The build process uses Next.js with Turbopack for faster compilation
- Tests run with a single worker for consistent, fast execution
