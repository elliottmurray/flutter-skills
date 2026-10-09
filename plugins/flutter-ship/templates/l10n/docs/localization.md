# Localization

English is the source language and the fallback for any device language the
app doesn't support. Every other language is a translation of
[`lib/l10n/app_en.arb`](../lib/l10n/app_en.arb). Read this before adding or
changing any text a user can see.

## Where a language lives

Each supported language has to appear in three places, and they have to
agree:

| Where | What | Kept in step by |
|---|---|---|
| `lib/l10n/app_<lang>.arb` | The strings | You, the Claude hook, `arb_parity_test.dart` |
| `ios/Runner/Info.plist` `CFBundleLocalizations` | Tells iOS the app speaks it; turns on Settings › App › Language | `scripts/l10n_locales.py` |
| `lib/l10n/app_localizations*.dart` | Generated Dart | `flutter gen-l10n` |

## Adding a string

1. Add the key to `lib/l10n/app_en.arb`. Add an `@key` block for placeholders,
   and a `description` when the English alone doesn't make the context clear.
2. Add the same key to every other `app_<lang>.arb`, translated. Don't paste
   the English in.
3. Run `flutter gen-l10n`. The generated files are committed, so
   `flutter analyze` works on a clean checkout. CI fails if they're stale.
4. Read it in a widget with `context.l10n.yourKey`
   (`import 'package:<app>/l10n/l10n.dart'`).

Changing an English value means changing every translation too, even though
the keys still match. Nothing can check that automatically, so the Claude hook
reminds you every time an ARB changes.

Counts use ICU plurals, never `n == 1 ? … : …`:

```json
"itemCount": "{count, plural, =1{1 item} other{{count} items}}"
```

Each language picks its own plural branches. French, for example, treats 0 as
singular, so its ARB adds `=0{0 article}`.

Store text that is shown in capitals in capitals in each ARB, so every
language controls its own casing.

## Adding a language

```bash
python3 scripts/l10n_locales.py add de        # or several: add de it pt pt_BR
```

This creates `app_de.arb` with every English string copied in, prints the keys
to translate, and adds `de` to `CFBundleLocalizations`. Translate every
string, then `flutter gen-l10n && flutter test test/l10n`. A regional variant
(`pt_BR`) also needs its base language (`pt`), because gen-l10n falls back to
it.

In Claude Code, `/localization add <lang>` does all of this, including the
translation.

## How sync is enforced

- **While editing (Claude Code):** the flutter-ship `l10n_parity_hook.py` runs
  after every ARB edit. It reports missing or extra keys, placeholder drift,
  and `CFBundleLocalizations` drift, and asks for the same change in every
  language. It is advisory and never blocks.
- **In `flutter test`:** `test/l10n/arb_parity_test.dart` fails on any missing
  key, extra key, placeholder mismatch, or plist that doesn't list exactly
  the ARB locales. `test/l10n/l10n_test.dart` checks English comes first, that
  unsupported locales fall back to English, and that each supported locale
  resolves.
- **In CI:** the Flutter workflow re-runs `flutter gen-l10n` and fails if the
  committed generated files differ.
- **Any time:** `python3 scripts/l10n_locales.py check` prints the same parity
  report without needing Flutter.

## What stays English

Log messages, exception text, analytics event names and values, persisted
enum names, and dev-only screens. Brand names are the same in every language.
Keep enum `.name`s English and map them to display text with an `l10n` helper,
because persistence and analytics depend on them.

## Strings outside widgets

A model that builds a sentence should take an `AppLocalizations` argument
instead of returning English. Tests pass
`lookupAppLocalizations(const Locale('en'))`.

## Widget tests

`context.l10n` falls back to English when no `AppLocalizations` delegate is in
the tree. A test that pumps a bare `MaterialApp` keeps working and can
`find.text` the English copy.

To test a translated screen, give the harness `locale`,
`AppLocalizations.localizationsDelegates` and
`AppLocalizations.supportedLocales`. For screens with fixed-width text, pump
each locale on the smallest supported iPhone (375 × 667) and assert there is
no overflow. German is often the longest language but not always. When a
translation overflows, prefer `FittedBox(fit: BoxFit.scaleDown)` over
clipping, and shorten the translation if it would shrink too far.

## Not covered by this setup

- iOS permission prompts (`NS*UsageDescription` in `Info.plist`) need
  `InfoPlist.strings` in each `<lang>.lproj`, added through Xcode.
- Backend responses and App Store metadata.

Machine-assisted translations are first drafts. Have a native speaker review
each ARB before you market the app in that language.
