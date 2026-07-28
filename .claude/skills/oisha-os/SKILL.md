```markdown
# oisha-os Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill provides guidance on contributing to the `oisha-os` TypeScript codebase. It covers established coding conventions, commit message patterns, and testing practices to ensure consistency and maintainability. While no specific frameworks or automated workflows are detected, this document outlines the project's standards and suggests helpful commands for common development tasks.

## Coding Conventions

### File Naming
- Use **camelCase** for all file names.
  - Example: `userProfile.ts`, `dataFetcher.test.ts`

### Import Style
- Use **relative imports** for referencing local modules.
  - Example:
    ```typescript
    import { fetchData } from './dataFetcher';
    ```

### Export Style
- Use **named exports** instead of default exports.
  - Example:
    ```typescript
    // In dataFetcher.ts
    export function fetchData() { /* ... */ }

    // In another file
    import { fetchData } from './dataFetcher';
    ```

### Commit Messages
- Use **conventional commits** with the `chore` prefix for routine changes.
  - Example:  
    ```
    chore: update dependencies to latest versions
    ```
- Average commit message length: ~65 characters.

## Workflows

_No automated workflows detected in this repository. Below are suggested manual workflows based on common development practices._

### Code Development
**Trigger:** When adding or updating features or bug fixes  
**Command:** `/dev-cycle`

1. Create a new branch for your feature or fix.
2. Implement changes following coding conventions.
3. Write or update corresponding test files (`*.test.ts`).
4. Commit changes using the conventional commit format.
5. Push your branch and open a pull request.

### Dependency Management
**Trigger:** When updating or adding dependencies  
**Command:** `/update-deps`

1. Run your package manager to update or add dependencies.
2. Test the codebase to ensure compatibility.
3. Commit with a message like `chore: update/add [dependency]`.
4. Push changes and create a pull request.

## Testing Patterns

- Test files use the pattern: `*.test.*` (e.g., `dataFetcher.test.ts`).
- The specific testing framework is not detected; ensure tests are colocated with or near the code they validate.
- Example test file:
  ```typescript
  // dataFetcher.test.ts
  import { fetchData } from './dataFetcher';

  test('fetchData returns expected result', () => {
    // ...test implementation
  });
  ```

## Commands

| Command        | Purpose                                             |
|----------------|-----------------------------------------------------|
| /dev-cycle     | Start a new development cycle for features or fixes |
| /update-deps   | Update or add project dependencies                  |
```
