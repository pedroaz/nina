<!--
SYNC IMPACT REPORT - Constitution Update
=========================================
Version Change: [NEW] → 1.0.0
Rationale: Initial constitution establishment defining core principles for code quality,
           testing standards, UX consistency, and performance requirements.

Modified Principles: N/A (Initial version)
Added Sections:
  - Core Principles (5 principles established)
  - Architecture Standards
  - Development Workflow
  - Governance

Templates Status:
  ✅ plan-template.md - Reviewed, no changes needed (constitution check placeholder exists)
  ✅ spec-template.md - Reviewed, compatible with principles
  ✅ tasks-template.md - Reviewed, compatible with test-first and quality principles

Follow-up TODOs: None

Created: 2025-10-27
-->

# Nina Project Constitution

## Core Principles

### I. Code Quality & Maintainability

Code MUST be written to be read and maintained, not just to work.

**Rules**:
- Every module MUST have a single, clear responsibility
- Functions MUST NOT exceed 50 lines; complexity beyond this requires justification
- Type safety MUST be enforced (TypeScript strict mode, no `any` types without explicit justification)
- Code MUST be self-documenting through clear naming; comments explain "why", not "what"
- All shared types and utilities MUST reside in `packages/shared` for cross-package reuse
- Linting and formatting rules MUST pass before commit (ESLint, Prettier)

**Rationale**: In a monorepo environment with Firebase and multiple packages, clarity and maintainability prevent technical debt accumulation and enable team scalability.

### II. Test-First Development (NON-NEGOTIABLE)

Tests define the contract before implementation begins, focused on business rules and user value.

**Rules**:
- ALL user-facing features MUST have Playwright E2E tests written FIRST that verify business rules and critical user journeys
- E2E tests MUST FAIL before implementation begins (Red-Green-Refactor)
- Firebase auth and database interactions MUST be tested against Firebase emulators
- Unit tests SHOULD be written in frontend (`packages/web-app/tests`) and backend (`packages/api-app/tests`) when they clarify business logic, edge cases, or complex algorithms
- Tests MUST verify business requirements and functionality, NOT implementation details
- Integration tests MUST cover cross-package communication and data flow in the monorepo
- DO NOT write tests for trivial code (getters, setters, simple mappings)
- Focus test effort on code that handles business rules, authentication, data validation, and critical business logic
- CI pipeline MUST block merges if tests fail

**Rationale**: Playwright E2E tests ensure user journeys work end-to-end. Firebase emulator testing prevents production dependencies during development. Test-first prevents scope creep and ensures verifiable requirements. Quality over coverage metrics—meaningful tests that catch real bugs are more valuable than 100% coverage of trivial code.

### III. User Experience Consistency

Users experience ONE product, not multiple disconnected interfaces.

**Rules**:
- Design system (shadcn/ui) MUST be the single source of truth for UI components
- All interactive elements MUST provide immediate feedback (loading states, error states, success states)
- Error messages MUST be user-friendly and actionable, not technical
- Accessibility MUST meet WCAG 2.1 AA standards (keyboard navigation, screen readers, contrast ratios)
- Loading states MUST appear for operations exceeding 200ms
- Offline states MUST be handled gracefully with clear user messaging
- Mobile-first responsive design MUST be implemented for all interfaces

**Rationale**: Consistency reduces cognitive load and builds user trust. Firebase's realtime nature requires thoughtful loading and error state handling.

### IV. Performance & Scalability

Performance is a feature, not an optimization phase.

**Rules**:
- Page load time MUST be under 2 seconds on 3G connections (Lighthouse score ≥90)
- Time to Interactive (TTI) MUST be under 3 seconds
- Firebase Firestore reads MUST be minimized through query optimization and caching
- Bundle size MUST be monitored; code splitting MUST be implemented for routes >500KB
- Images MUST be optimized (WebP format, lazy loading, responsive sizes)
- Firebase auth state MUST be cached to avoid unnecessary network calls
- Database indexes MUST be created for all query patterns before production deployment

**Rationale**: Firebase pricing is usage-based; inefficient queries directly impact costs. Users on slower connections must still have a usable experience.

### V. Security & Privacy First

Security is built in, not bolted on.

**Rules**:
- Firebase Security Rules MUST be defined and tested before feature deployment
- Authentication state MUST be verified server-side (Firebase Admin SDK) for sensitive operations
- Environment variables MUST NEVER be committed (`.env` files in `.gitignore`)
- API keys MUST use Firebase App Check for abuse prevention
- User data MUST follow principle of least privilege (minimal data collection, clear retention policies)
- All user inputs MUST be validated and sanitized before database writes
- Security Rules MUST be tested with Firebase emulator suite

**Rationale**: Firebase's security model relies on client-side and server-side rules working together. Misconfigured rules expose data; testing prevents production vulnerabilities.

## Architecture Standards

### Monorepo Structure

The project MUST maintain the following structure:

```
nina/
├── packages/
│   ├── shared/          # Shared types, utilities, helper functions
│   ├── web-app/         # Next.js application (with own tests/)
│   └── api-app/         # Backend API services (with own tests/)
└── tests/
    └── e2e/             # Playwright E2E tests (root level)
```

**Constraints**:
- `packages/shared` contains ONLY types and utility functions reusable across frontend and backend
- `packages/shared` MUST NOT depend on `web-app` or `api-app` (unidirectional dependency)
- Frontend unit tests MUST live in `packages/web-app/tests`
- Backend unit tests MUST live in `packages/api-app/tests`
- Cross-package dependencies MUST be explicit in `package.json`
- Shared types MUST live in `packages/shared/src/types`

### Firebase Integration

**Authentication**:
- Firebase Authentication MUST be the single source of truth for user identity
- Auth state MUST be managed in a React Context (`packages/web-app/src/contexts/AuthContext`)
- Protected routes MUST use auth middleware/guards

**Database**:
- Firestore MUST be used for structured data
- Realtime Database MAY be used only for highly volatile data (chat, presence)
- Database schema MUST be documented in `/docs/database-schema.md`

**Testing**:
- Firebase emulators MUST be used for all local development and testing
- Emulator data MUST be seeded for consistent E2E test execution

## Development Workflow

### Feature Development

1. **Specification**: Define user stories with acceptance criteria (spec-template.md)
2. **Planning**: Technical design including database schema, API contracts (plan-template.md)
3. **Test Writing**: Write failing Playwright E2E tests for critical user journeys and business rules
4. **Implementation**: Build feature to pass tests
5. **Review**: Code review verifies constitution compliance
6. **Deployment**: CI pipeline runs all tests; merge only on success

### Code Review Requirements

All PRs MUST:
- Pass all linting and formatting checks
- Pass all tests (unit, integration, E2E)
- Include tests for business-critical functionality
- Update documentation if public APIs changed
- Be reviewed by at least one other developer
- Reference related issue/story in PR description

### Commit Standards

- Commit messages MUST follow Conventional Commits format:
  - `feat:` for new features
  - `fix:` for bug fixes
  - `test:` for test additions/changes
  - `docs:` for documentation updates
  - `refactor:` for code refactoring
  - `perf:` for performance improvements
  - `chore:` for maintenance tasks

### Branch Strategy

- `main` branch MUST always be deployable
- Feature branches MUST follow pattern: `###-feature-name`
- Hotfix branches MUST follow pattern: `hotfix/###-description`
- All merges to `main` MUST be via Pull Request

## Governance

### Constitution Authority

This constitution supersedes all other development practices and guidelines. When conflicts arise, constitution principles take precedence.

### Amendment Process

Constitution amendments REQUIRE:
1. Written proposal documenting rationale and impact
2. Team review and consensus
3. Version increment following semantic versioning
4. Migration plan for existing code if breaking changes introduced
5. Update to all dependent templates and documentation

### Compliance Verification

- All PRs MUST include a constitution compliance checklist
- Quarterly reviews MUST audit codebase for principle adherence
- Violations MUST be justified in writing or immediately remediated
- Complexity additions (new patterns, abstractions) MUST be justified against simpler alternatives

### Versioning Policy

Constitution versions follow MAJOR.MINOR.PATCH:
- **MAJOR**: Backward-incompatible governance changes or principle removals
- **MINOR**: New principles added or existing principles expanded
- **PATCH**: Clarifications, wording improvements, typo fixes

### Enforcement

- CI pipeline MUST enforce automated rules (linting, tests, coverage)
- Code reviews MUST verify subjective principles (clarity, maintainability)
- Team leads MUST resolve disputes by referencing constitution principles
- Persistent violations MUST trigger process review and team discussion

**Version**: 1.0.0 | **Ratified**: 2025-10-27 | **Last Amended**: 2025-10-27
