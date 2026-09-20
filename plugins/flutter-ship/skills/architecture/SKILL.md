---
name: architecture
description: >
  Review changed code against the layered architecture — MVVM plus
  repository in Flutter, transport/logic/data in the API — and fix the
  mechanical drift. Trigger on /architecture, architecture review,
  layering, ViewModel, repository pattern, "where should this code live",
  or a widget calling an API directly.
user_invocable: true
---

# Architecture

A review pass over **what changed**, not a whole-repo audit. Default scope
is the diff against `HEAD`, so this runs the same way before a commit as
`/tdd` does after one.

This is the **review** direction: it ends in a verdict, not a scaffold. For
building a new feature forward from nothing, `flutter-apply-architecture-best-practices`
in [flutter/agent-plugins](https://github.com/flutter/agent-plugins) is the
generative path over the same doctrine; step 5 below is that workflow extended
across the client/API contract.

Both sides of the wire are in scope. A ViewModel that builds URLs and a
route handler that runs a query are the same mistake, and the contract
between them is where layering actually breaks.

The app's `CLAUDE.md` wins where it disagrees with this skill: read its
**Architecture** section if it has one and follow that. The rules below
are the default for a project that has not written one yet.

## Usage

```
/architecture [--all] [--fix]
```

## 1. Scope

Resolve the scope in this order, then print which one you picked and the
file count before reviewing anything.

1. **Uncommitted work** — `git status --porcelain` is non-empty:

   ```bash
   git diff HEAD --name-only
   git ls-files --others --exclude-standard
   ```

2. **Otherwise the branch** — `git diff main...HEAD --name-only`.

3. **`--all`** — every tracked source file. Say up front that this is a
   backlog, not a gate: on an app that predates the skill it will find a
   lot, and none of it is a reason to stop the current change.

Split the paths by toolchain. Do not hardcode `lib/` and `backend/`:

```bash
python3 scripts/project_layout.py --json
```

A path is Python if it ends in `.py` or sits under one of
`python_packages`; otherwise it is Dart. If the script is missing (the
project was not rendered by `/setup-project`), fall back to `lib/` and
`backend/` and say you did.

Read the changed files before judging them. A diff hunk does not show
which layer the file is in.

## 2. Flutter layers

UI is MVVM; data is the repository pattern; the domain layer is optional
and earns its place or stays out.

| Layer | Lives in | May depend on | Must not |
|---|---|---|---|
| **View** | `lib/ui/features/<feature>/views/` | its ViewModel, `lib/ui/core/` | fetch data, hold business state, import a service or `http`/Firebase |
| **ViewModel** | `lib/ui/features/<feature>/view_models/` | repositories, use cases, domain models | build widgets, touch `BuildContext`, import a service directly |
| **Repository** | `lib/data/repositories/` | services, domain + API models | import anything under `lib/ui/` |
| **Service** | `lib/data/services/` | `http`, Firebase, platform plugins | know about domain models or widgets |
| **Use case** | `lib/domain/use_cases/` | repositories | exist for plain CRUD |

```text
lib/
├── config/             # flag_registry.dart, app_channel.dart (Firebase projects)
├── data/
│   ├── models/         # API models — the wire shape
│   ├── repositories/   # single source of truth per domain concept
│   └── services/       # API clients, local storage, platform wrappers
├── domain/
│   ├── models/         # domain models — what the app means
│   └── use_cases/      # optional
└── ui/
    ├── core/           # shared widgets, theme, typography
    └── features/<feature>/{view_models,views}/
```

Rules that matter more than the folder names:

- **Views take their ViewModel by constructor** and rebuild through
  `ListenableBuilder`. State exposed to a View is immutable.
- **ViewModels take repositories by constructor.** No locator lookups
  inside methods — that is what makes them untestable.
- **Repositories return domain models**, never the API model. The
  transform is the point of the repository; a repository that returns
  `UserApiModel` is a service with a longer name.
- **Services are stateless.** Caching, retries and offline sync live in
  the repository.
- Register the service, the repository and the ViewModel in whatever DI
  the project already uses.

On an app that does not have this structure, do not mass-move files.
Apply the layering to the feature that changed and note the drift. The
one rule with no grace period: **no data access from a widget.**

State management is not the point. `ChangeNotifier` + `ListenableBuilder`
is the default because it ships with Flutter; if the project already uses
Riverpod, Bloc or signals, keep it and read "ViewModel" as whatever that
library calls the same seam.

## 3. Backend layers

Pick the reference by what the repo actually has, then review the
non-Dart changes against it:

```bash
python3 scripts/project_layout.py --python-dir     # e.g. backend
grep -l fastapi backend/pyproject.toml 2>/dev/null
```

- **FastAPI** — [backends/fastapi.md](backends/fastapi.md)
- **Anything else**, including an API in another repo —
  [backends/other.md](backends/other.md)
- **No backend** — skip to step 4 and review the Dart side only.

Read only the file that applies.

## 4. The contract between them

Check this even when only one side changed.

- **One Dart service owns the API client.** Base URL, headers, timeouts
  and the App Check header live there once. A ViewModel that builds a URL
  is the bug, not the endpoint.
- **A response-shape change on the server needs the matching API model,
  repository transform and test in the same change.** `/pr-review` grades
  this high risk for good reason: the client ships weeks later than the
  API does.
- **Do not mirror server schemas into the View.** The domain model is
  allowed to be smaller, flatter and differently named than the wire.
- **Errors become domain failures at the repository boundary.** An HTTP
  status or a `DioException` reaching a widget is a layering break. Map
  to a `Result`/failure type in the repository.
- **Nullability and defaults are decided once**, in the transform — not
  with `?? ''` scattered through the widget tree.
- Endpoints the client calls must be gated the way `/app-check` expects;
  new public routes should be deliberate.

## 5. New feature workflow

Back to front — the layer with no dependents goes first. Copy this and
tick it off; drop the backend steps when the feature is client-only.

### Task Progress

- [ ] **1. Agree the contract.** Path, request, response, error cases.
      Write it down before either side is built.
- [ ] **2. Backend data + logic.** Repository/store, then the service
      that uses it. Tests first (`/tdd`).
- [ ] **3. Backend transport.** Route, schema, auth dependency,
      declared response model.
- [ ] **4. Dart domain models.** Immutable; `freezed` only if the
      project already uses it.
- [ ] **5. Dart service.** The typed call against the endpoint from
      step 3.
- [ ] **6. Dart repository.** Consume the service, transform to domain
      models, own caching and failure mapping.
- [ ] **7. Use case** — only if the logic is complex or shared across
      ViewModels. Plain CRUD skips this.
- [ ] **8. ViewModel.** Repositories injected, immutable state out,
      commands in.
- [ ] **9. View.** `ListenableBuilder`, no logic beyond layout.
- [ ] **10. Wire up DI** for the new service, repository and ViewModel.
- [ ] **11. Run the gates.** `flutter analyze`, `flutter test`, and the
      backend's lint + tests. Loop until green.

## 6. Report

```
## Scope
## Flutter findings
## Backend findings          (omit when no backend file changed)
## Client/API contract
## Verdict
```

One line per finding: `path:line — <rule broken> → <smallest move that
fixes it>`. Name the rule; "feels wrong" is not a finding.

Verdict is exactly one of:

- **clean** — changed files sit in the right layers.
- **drift** — nothing crosses a boundary, but files are in the wrong
  place or a layer is doing a neighbour's job. Fix when convenient.
- **violation** — a boundary is crossed: data access in a widget, a
  route with business logic in it, a shape change with no client update.
  Fix before merging.

Print only, unless `--fix`. With `--fix`, apply the **mechanical** moves
only — lift a service call out of a widget into the repository or
ViewModel, move a file into its layer, update imports, add the missing
transform — then run `flutter analyze` and `flutter test` (plus the
backend gates if Python changed) and report what you left behind.
Anything needing a design decision stays in the report.

## Do not

- Restructure the whole app in one pass because `--all` found things
- Swap the project's state management or DI library
- Add `freezed`, `get_it` or Riverpod because an example uses them
- Create `domain/use_cases/` for CRUD
- Hardcode `lib/` or `backend/` — ask `scripts/project_layout.py`
- Re-do `/pr-review`: risk tiers, CI status and file growth are its job
- Report a violation without the one-move fix next to it
