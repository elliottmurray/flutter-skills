# Releasing lastmile

lastmile reaches people two ways:

| Channel | Who it reaches | How they install | How updates arrive |
|---|---|---|---|
| **This repo as a marketplace** | Claude Code users | `/plugin install lastmile --marketplace elliottmurray/lastmile` | `claude plugin update lastmile@lastmile`, or auto-update if they turned it on |
| **Anthropic's directory** | claude.ai, Cowork and Claude Code users (loads in Claude Code as `lastmile@synced`) | "Add" on the listing at [claude.ai/directory](https://claude.ai/directory) | The directory scans the `release` branch and publishes versions that pass |

The first channel needs nothing beyond this repo being public. The second
needs a one-time submission, then CI keeps it current.

`claude-plugins-official`, the marketplace Claude Code adds by default, is
curated by Anthropic and takes no submissions. The directory is the public
route.

The plugin lives at the **repo root**: `.claude-plugin/plugin.json` beside
`skills/`, `hooks/`, `templates/` and `scripts/`. `marketplace.json` points at
it with `"source": "./"`. This layout matters for the directory (see
[Review holds](#review-holds)).

## How a release works

A release is **a merge to `main` that changes `version` in
`.claude-plugin/plugin.json`**. Nothing else ships.

```
PR bumps version ──► Plugin CI (validate, preflight, tests)
        │
        ▼ merge
main ──► Plugin release workflow
           ├─ validate again
           ├─ tag lastmile--v<version>   (claude plugin tag)
           ├─ GitHub release with generated notes
           └─ fast-forward `release` branch ──► directory webhook ──► scan ──► publish
```

- Marketplace users get the new version because `version` changed. Claude
  Code compares versions, so a merge without a bump gives them nothing.
- The directory tracks `release`, not `main`. Merges that don't bump the
  version never reach it.

So you can merge several PRs to `main` and release them together with one
bump PR. On a PR that changes shipping files (anything outside `.github/`,
`docs/` and `*.md`) without a bump, Plugin CI posts a warning, not a failure.

### Cutting a release

1. Open a PR that sets the new `version` in `plugin.json`. Use semver: patch
   for fixes and wording, minor for new skills or templates, major for
   changes that break projects already rendered by `/setup-project`.
2. Wait for **Plugin CI** to go green, then merge.
3. **Plugin release** runs on the merge. Check the Actions tab for the tag
   and the GitHub release.
4. Directory only: if a version is held for review, it shows on the
   plugin's page in the [developer portal](https://claude.ai/directory/manage).

To re-run a release that failed partway, use **Run workflow** on Plugin
release. It skips everything if the tag already exists, so delete a
half-made tag first (`git push origin :refs/tags/lastmile--vX.Y.Z`).

## Checking locally

```bash
claude plugin validate --strict .                         # marketplace.json
claude plugin validate --strict .claude-plugin/plugin.json # plugin.json
python3 scripts/plugin_preflight.py --base main           # directory rules + bump check
```

`plugin_preflight.py` covers the directory rules that can be checked offline:
README of at least 40 words, a licence, `author`, semver, no `.DS_Store` or
symlinks, no non-image file over 256 KiB, no stray binaries, at most 512
files, and file names that work on Windows. It reads git-tracked files only,
so `git add` new files first. The portal's **Validate** button runs more
checks than this script and has the final say.

## One-time setup

### 1. Rename the repo

The repo is renamed to `lastmile` in GitHub under **Settings → General →
Repository name**. GitHub redirects the old URL, so existing clones and
links keep working. Then update your clone:

```bash
git remote set-url origin git@github.com:elliottmurray/lastmile.git
```

Do this **before** submitting to the directory. A submission is locked to its
repository and folder; changing either means withdrawing and resubmitting.

### 2. Repository settings

- **Actions → General → Workflow permissions**: either setting works, since
  the release workflow asks for `contents: write` itself. If an org policy
  caps tokens at read-only, the tag push will fail and you need to lift the
  cap.
- **Don't protect `release`** with rules that block `github-actions[bot]`.
  If you want a ruleset on it, add GitHub Actions as a bypass actor. The
  workflow only fast-forwards, so it can't rewrite history there.
- The first release creates `release`. To submit to the directory before
  that, create it by hand: `git push origin main:release`.

### 3. Submit to the directory

You need a paid claude.ai plan (Pro or Max submits from your own account;
on Team or Enterprise an Owner submits) and your GitHub account connected
in claude.ai, with push access to this repo.

1. Open [claude.ai/directory/manage](https://claude.ai/directory/manage),
   select **Submit new**, then **Plugin bundle**.
2. **Source**:
   - Repository: `elliottmurray/lastmile`
   - Plugin path: leave empty (the plugin is at the repo root)
   - Branch or tag: `release`

   Select **Validate**. A **Name is taken** finding means another
   organization uses `lastmile`; pick a new name before going further (see
   [Maintenance](#maintenance) on renaming). Fix anything marked
   **Blocking**, push it to `main`, cut a release (or
   `git push origin main:release`), and select **Re-validate**.
3. **Listing details** come from `plugin.json` (`displayName`, `description`)
   and `README.md`. To change them, edit those files and release.
4. **Data handling**: the plugin stores no personal data, sends nothing to
   third parties, and keeps nothing. Answer the under-18 question for your
   own intended audience.
5. **Compliance**: confirm the contact email and tick the four
   acknowledgements.
6. **Review and submit**: keep **GitHub push webhook**, decide on
   **Auto-publish passing versions** (on means later releases go live
   without you pressing Publish), then **Submit for review**.
7. On the next page select **Set up push updates** (needs admin on the
   repo). Without the webhook the directory still finds new commits on its
   schedule, just later. You can do this later under **Settings → Updates**.

Once the first version passes, select **Publish**. An Anthropic reviewer
publishes the first version.

### Review holds

A hold means a reviewer reads that version before it goes live. It is not a
rejection, but it can come back on each new version.

With the plugin at the repo root, the usual hold for Python hooks
("Scripts the validator couldn't follow") should not apply: that check only
fires when the plugin is a subfolder of its repository. If it still appears,
make each hook a shell script that names every path as
`${CLAUDE_PLUGIN_ROOT}/<file>`.

The plugin's README spells out what each hook and script does, because the
security scan checks that behaviour is disclosed. Update the
"What it runs on your machine" section whenever a hook or script changes.

## Maintenance

- **Claude Code CLI version.** Both workflows pin `CLAUDE_CODE_VERSION`.
  Bump it now and then; new versions sometimes add validation warnings, and
  `--strict` turns those into failures.
- **Renaming the plugin** changes what everyone has installed
  (`lastmile@lastmile`) and, once listed, what the directory knows it as.
  Rename only before anyone else has installed it. Change `displayName` for
  a new label instead.
- **Release branch diverged** (push rejected as non-fast-forward): someone
  committed to `release` directly. Reset it to the last tag on `main` by hand
  (`git push --force origin lastmile--vX.Y.Z:refs/heads/release`), then
  re-run the workflow.

## References

- [Publish and distribute a plugin](https://code.claude.com/docs/en/plugins/publish)
- [Submit your plugin](https://claude.com/docs/plugins/submit) to the directory
- [Plugin pre-submission checklist](https://claude.com/docs/plugins/pre-submission-checklist)
- [Anthropic's marketplaces](https://code.claude.com/docs/en/plugins/anthropic-marketplaces)
