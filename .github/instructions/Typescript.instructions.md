# TypeScript Development Style Guide

**applyTo:** `packages/web-app/**/*.ts,src/**/*.tsx`

## General Principles
- Apply the [general coding guidelines](./general-coding.instructions.md) to all TypeScript code
- Use strict TypeScript configuration (`strict: true`)
- Avoid `any` types; use proper type annotations
- Prefer interfaces over type aliases for object shapes

## Code Style
- Use `const` by default, `let` only when reassignment is needed
- Use arrow functions for callbacks and functional programming
- Maintain consistent naming: `camelCase` for variables/functions, `PascalCase` for types/classes
- Keep functions focused and under 20 lines when possible
- Use meaningful variable and function names

## Type Safety
- Always explicitly type function parameters and return types
- Use union types and discriminated unions for complex data
- Leverage utility types for derived types (`Pick`, `Omit`, `Record`, etc.)
- Avoid casting; use proper typing instead

## Best Practices
- Use destructuring for imports and object/array access
- Prefer early returns to reduce nesting
- Use `readonly` for immutable properties
- Document complex logic with inline comments