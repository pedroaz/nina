# Repository Structure

This repository is a monorepo managed with **pnpm workspaces**. It houses multiple packages that work together to form the Nina platform.

## Directory Layout

### Root
- **package.json**: Defines the workspace and root scripts.
- **pnpm-workspace.yaml**: Configures the pnpm workspace.
- **.agent/**: Contains agent-specific documentation and context (this directory).

### Packages (`packages/`)
The core logic and applications are located in the `packages/` directory:

- **`web-app`** (`packages/web-app`):
  - The main web application for Nina.
  - Built with Next.js (App Router).
  - Handles user interface, authentication, and core application features.

- **`landing-page`** (`packages/landing-page`):
  - The public-facing landing page for the product.
  - Built with Next.js.
  - Showcases features and provides entry points to the app.

- **`core`** (`packages/core`):
  - Shared business logic, database connections, and utilities.
  - Used by both `web-app` and potentially other services.
  - Contains Genkit configuration, database schemas, and entities.

## Workspace Management
- Dependencies are managed at the root and within each package.
- `pnpm` is used for efficient dependency installation and linking between workspace packages.
