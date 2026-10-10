---
name: pr-review
description: >
  Review a pull request and assign a risk tier. Trigger on /pr-review,
  reviewing a PR, or whether a change is safe to merge.
user_invocable: true
---

# PR Review

Review a change for correctness and security, then assign exactly one
risk tier. `/setup-project` already copies `claude.yml`, so `@claude` on
a PR comment runs Claude Code Action — keep that workflow. This skill is
the rubric those reviews should follow.

Project-specific danger areas live in the app's `CLAUDE.md` (section
**Danger areas**). Read that file if it exists; do not invent a second
list. The defaults below apply when the section is still the template.

## Usage

```
/pr-review [PR#] [--apply]
```

Resolve the mode, in this order:

1. **PR# given** — review that PR.
2. **No PR#, current branch has an open PR** —
   `gh pr view --json number -q .number`
3. **No open PR — pre-PR local mode.** Review `git diff main...HEAD`.
   Always print-only, even if `--apply` was passed: "No open PR yet —
   this is a pre-PR assessment; nothing was posted."

`gh` infers the repo from the current remotes. Do not add `--repo`.

## Steps

1. **Read the change.**
   - PR: `gh pr view <number>` and `gh pr diff <number>`
   - Pre-PR: `git diff main...HEAD`

2. **Code review** — correctness, security, obvious simplification.
   Proportionate: a gate, not a deep audit.

3. **Test coverage.** A behaviour change with no matching test change is
   a gap. Flutter tests live under `test/` / `integration_test/`; Python
   under `backend/tests/` when that tree exists.

4. **Large file growth** (flag only; do not refactor in this pass):

   ```bash
   # PR
   base=$(gh pr view <number> --json baseRefName -q .baseRefName)
   head=$(gh pr view <number> --json headRefName -q .headRefName)
   git fetch origin "$base" "$head"
   git diff "origin/$base...origin/$head" --numstat

   # Pre-PR
   git diff main...HEAD --numstat
   ```

   Skip `*.g.dart` / `*.freezed.dart` and binary/deleted rows (`-`).
   Flag when **either**:
   - current total `>= 1000` and the file did not shrink (`added >= removed`)
   - `<added> >= 50` and current total `>= 800`

   A net shrink of a 1000-line file is not a flag.

5. **CI** (PR mode only): `gh pr checks <number>`. If checks are pending,
   wait once and re-check; do not loop. No checks (docs-only) is "no CI
   signal", not "passing". Skip in pre-PR mode.

6. **Assign exactly one tier** using [the rubric](#risk-rubric).

7. **Report** with `## Summary`, `## Review findings`,
   `## Test & lint status`, `## Large file growth` (omit if step 4
   flagged nothing), `## Risk: <low|medium|high>`, `## Recommendation`.

   - Pre-PR, or PR without `--apply`: print in the conversation only.
   - PR with `--apply`: create `risk:low` / `risk:medium` / `risk:high`
     labels if needed, post one comment, set exactly one `risk:*` label.
     **Never merge.** Do not take a PR out of draft unless the caller
     explicitly asks.

## Risk rubric

**high** — any of:

- Touches `.github/workflows/**`, `.claude/**`, or git hooks.
- Secrets, signing, App Check, or credential handling.
- A `release` flag default flipped to the shipped value without a
  matching Remote Config graduate (see `/feature-flags`).
- FastAPI request/response shape change with no matching Flutter client
  update (when `backend/` exists).
- Anything listed as high-risk in the project's `CLAUDE.md` danger areas.
- Failing CI, or a behaviour change with no tests.

**medium** — backward-compatible behaviour change outside the areas
above, tests reasonable, CI green or genuinely N/A.

**low** — purely additive, has tests, CI green, touches none of the
high-risk areas.

Large-file flags do not change the tier by themselves. Ask whether to
split in a follow-up commit.
