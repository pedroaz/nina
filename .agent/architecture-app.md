# Web App Architecture

The `web-app` package is the primary user interface for Nina. It is built using **Next.js** with the **App Router**.

## Tech Stack
- **Framework**: Next.js 15
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State Management**: Zustand
- **Validation**: Zod
- **Icons**: Lucide React
- **UI Components**: Radix UI primitives

## Directory Structure (`packages/web-app`)

- **`app/`**: Contains the application routes, layouts, and pages (App Router).
- **`components/`**: Reusable UI components.
  - Likely organized by atomic design or feature-based structure.
- **`hooks/`**: Custom React hooks.
- **`lib/`**: Utility functions and shared libraries.
- **`stores/`**: Zustand state management stores.
- **`types/`**: TypeScript type definitions.
- **`public/`**: Static assets.

## Key Patterns
- **Server Components**: Leveraged for data fetching and initial rendering where possible.
- **Client Components**: Used for interactive elements (marked with `'use client'`).
- **Path Aliases**:
  - `@/*` maps to `./*`
  - `@core/*` maps to `../core/*` (accessing shared core logic).

## Integration
- Imports shared logic and types from the `core` package.
