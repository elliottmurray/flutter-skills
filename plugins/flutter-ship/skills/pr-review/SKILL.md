---
name: pr-review
description: >
  Review a pull request and assign a risk tier. Trigger on /pr-review,
  reviewing a PR, or whether a change is safe to merge.
user_invocable: true
---

# PR Review

**Not shipped yet.** `/setup-project` copies `claude.yml` so `@claude` on
a PR comment already runs Claude Code Action. This skill will add a
repo-specific rubric.

## What this skill will do

- `gh pr view` / `gh pr diff` (or `git diff main...HEAD` pre-PR)
- Correctness and security review, proportionate
- Test-coverage gap check
- Risk tier using danger areas filled in at setup (not generic categories)
- Optional `--apply`: comment, label, never merge
