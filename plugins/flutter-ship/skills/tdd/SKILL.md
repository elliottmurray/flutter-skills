---
name: tdd
description: >
  Develop features and fixes using Test-Driven Development — write failing
  tests first, then implement code to pass them. Use when the user asks for
  TDD, /tdd, a failing test first, or red-green-refactor.
user_invocable: true
---

# TDD Skill

Follow the Red-Green-Refactor cycle for the requested change. Apply TDD
where practical — skip it for trivial changes, boilerplate, or pure UI
layout that cannot be meaningfully unit tested.

## Process

1. **Understand the change** — Read the relevant source files and existing
   tests to understand current behavior and test patterns used in this
   project.

2. **Red — Write a failing test first**
   - Add a test (or tests) in the appropriate `test/` file that describes
     the desired behavior.
   - Follow the existing test style: `flutter_test`, `group()`/`test()`
     structure, same import patterns. For a FastAPI `backend/`, use pytest
     the same way.
   - Run the test to confirm it fails:
     ```
     flutter test <test_file>
     ```
     or `uv run pytest <test_file>` in `backend/`.
   - Show the user the failing test output.

3. **Green — Write the minimum code to pass**
   - Implement only enough production code to make the failing test pass.
   - Run the test again to confirm it passes.
   - If it still fails, iterate on the implementation (not the test) until
     green.

4. **Refactor — Clean up while tests stay green**
   - Look for duplication or clarity improvements in both test and
     production code.
   - Run tests after any refactor to ensure nothing broke.

5. **Repeat** — If the feature needs more behavior, go back to step 2 with
   the next test case.

## When to skip TDD

- Pure widget layout/styling with no logic
- Simple config or constant changes
- Auto-generated code
- Changes where the test would just duplicate the implementation

When skipping, say why and still run existing tests to avoid regressions:

```
flutter test
```

## Guidelines

- One logical assertion per test where practical.
- Test names should describe behavior, not implementation
  (`should reject duplicate values in row`, not `test setValue method`).
- Prefer testing public API over internals.
- Keep tests independent — no shared mutable state between tests.
- If a widget has testable logic, extract it and unit test the logic even
  if you skip the widget test.
