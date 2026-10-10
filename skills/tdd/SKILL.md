---
name: tdd
description: >
  Test-first development for Flutter and a FastAPI backend: write a test for
  the next behaviour, watch it fail, make it pass, tidy up, repeat. Use when
  the user asks for TDD, /tdd, a failing test first, or tests before code.
user_invocable: true
---

# Test-first development

This skill puts a failing test in front of every behaviour change. It is
test-first, not strict red-green-refactor: it does not insist on the
smallest possible step, and refactoring is a check at the end of each
cycle rather than a separate phase. What it does guarantee is that no
behaviour lands without a test that was seen failing first.

Skip it for trivial changes, boilerplate, or pure UI layout that cannot be
meaningfully unit tested.

This skill owns the **process**. Where they are installed, defer the mechanics
to `dart-add-unit-test` (file layout, `package:test` idiom),
`dart-generate-test-mocks` and `flutter-add-widget-test`. Backend pytest has no
upstream counterpart, so it stays here.

## Process

1. **Understand the change.** Read the relevant source files and existing
   tests to understand current behaviour and the test patterns this
   project uses. Split the change into behaviours you can test one at a
   time, and say what the list is.

2. **Write a failing test for the next behaviour.**
   - Add the test in the appropriate `test/` file. Usually that is one
     test; a couple is fine when they pin down the same behaviour from
     both sides (valid and invalid input, say).
   - Follow the existing test style: `flutter_test`, `group()`/`test()`
     structure, same import patterns. For a FastAPI `backend/`, use pytest
     the same way.
   - Run it:
     ```
     flutter test <test_file>
     ```
     or `uv run pytest <test_file>` in `backend/`.
   - Check it fails for the right reason. In Dart a test that calls a
     method that does not exist yet fails to compile, which proves
     nothing about behaviour. Add a stub that compiles (returns a wrong
     value or throws `UnimplementedError`) and run again until the
     failure is the assertion you wrote.
   - Show the user the failing output.

3. **Make it pass.**
   - Write the production code for that behaviour. Keep it to what the
     test asks for; do not build ahead for behaviours later in the list.
   - Run the test again to confirm it passes.
   - If it still fails, change the implementation, not the test. Change
     the test only if it was wrong about the behaviour, and say so.

4. **Tidy up.**
   - Look for duplication or unclear names in both the test and the code
     just written. Fix what is there; do not start a wider refactor.
   - Run the test file again after any change.

5. **Repeat** from step 2 with the next behaviour on the list. When the
   list is done, run the whole suite (`flutter test`, and `uv run pytest`
   if there is a backend).

## How this differs from strict TDD

Say this if the user asks for red-green-refactor by name:

- Steps are sized by behaviour, not by the smallest change that turns a
  test green. There is no deliberate fake-it-then-generalise step.
- Refactoring is a short tidy at the end of each cycle, not its own phase
  with its own commit.
- A stub to get past a compile error is allowed so the red step shows a
  real assertion failure.

If they want the strict version, follow it: one assertion-level test at a
time, the least code that passes, and refactor only on green.

## When to skip

- Pure widget layout/styling with no logic
- Simple config or constant changes
- Auto-generated code
- Changes where the test would just duplicate the implementation

When skipping, say why and still run the existing tests to catch
regressions:

```
flutter test
```

## Guidelines

- One logical assertion per test where practical.
- Test names describe behaviour, not implementation
  (`rejects duplicate values in a row`, not `test setValue method`).
- Prefer testing public API over internals.
- Keep tests independent, with no shared mutable state between them.
- If a widget has testable logic, extract it and unit test the logic even
  if you skip the widget test.
