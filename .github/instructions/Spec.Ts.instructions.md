---
applyTo: "tests/**/*.ts,tests/**/*.tsx"
---
# Playwright Testing Style Guide

Apply the [general coding guidelines](./general-coding.instructions.md) to all test code.

## Playwright Test Guidelines
- Use TypeScript for all test files
- Follow the Arrange-Act-Assert (AAA) pattern
- Use descriptive test names that clearly state what is being tested
- Keep tests focused and independent
- Use page fixtures and test utilities for common operations
- Prefer `expect()` assertions with clear matchers
- Organize tests in logical test groups using `describe()` blocks
- Avoid hardcoded waits; use Playwright's built-in waiting mechanisms
- Use meaningful variable names in test setup and teardown

## Best Practices
- One assertion per test when possible
- Mock external dependencies appropriately
- Clean up resources in `afterEach()` hooks
- Use `page.goto()` and navigation helpers consistently
- Document complex test scenarios with comments