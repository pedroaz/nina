# Agent Entry Point

Welcome, Agent. This file serves as your primary entry point to the Nina codebase.

## Documentation Overview

Before starting any task, consult the relevant documentation files in this directory:

- **[features.md](./features.md)**: Understand the product's core value proposition and features.
- **[repository.md](./repository.md)**: Familiarize yourself with the workspace structure and package layout.
- **[stack.md](./stack.md)**: **CRITICAL**. Review the technology stack and versions. Do not introduce incompatible libraries or patterns.
- **[role.md](./role.md)**: Internalize your role as a Senior Fullstack Developer.
- **[architecture-app.md](./architecture-app.md)**: Consult this when working on the `web-app` package.
- **[design-system.md](./design-system.md)**: **CRITICAL**. Consult this for UI/UX guidelines, component usage, and styling standards for the `web-app`.
- **[architecture-landing-page.md](./architecture-landing-page.md)**: Consult this when working on the `landing-page` package.

## Reminders

1.  **Update Documentation**: If you make changes that affect the architecture, stack, or features, you **MUST** update the corresponding documentation file.
2.  **Follow the Role**: Adhere strictly to the principles defined in `role.md`.
3.  **Check the Stack**: Always verify versions in `stack.md` before suggesting code or installing packages.
4. **Verify Build, Lint, and Tests**: Before submitting any changes, always ensure the build is working, there are no linting errors, and all Playwright tests are passing. See **[verify.md](./verify.md)** for the verification workflow.