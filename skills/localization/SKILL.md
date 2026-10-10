---
name: localization
description: >
  Set up Flutter gen-l10n, add a language, and keep every translation in sync
  with English. Use on /localization, "add French", "translate the app",
  "localise", "l10n", "i18n", "ARB", missing translations, or when
  /setup-project chose localization.
user_invocable: true
---

# Localization

English (`lib/l10n/app_en.arb`) is the template. Every other language is an
`app_<lang>.arb` with exactly the same keys and placeholders, and is listed in
the iOS `CFBundleLocalizations`. This skill sets that up and keeps it true.

Plugin root: `${CLAUDE_PLUGIN_ROOT}`. Project script: `scripts/l10n_locales.py`
(rendered by `/setup-project --l10n`). Run everything from the Flutter package
root (`python3 scripts/project_layout.py --dart-dir`).

What enforces sync, so you know what will catch a slip:

| When | What | Blocks? |
|---|---|---|
| After any ARB edit | `l10n_parity_hook.py` (this plugin): missing/extra keys, placeholder drift, plist drift, plus a reminder to change every language | No |
| `flutter test` | `test/l10n/arb_parity_test.dart`, `test/l10n/l10n_test.dart` | Yes |
| CI lint job | `flutter gen-l10n` then fail on a diff under `lib/` | Yes |
| Any time | `python3 scripts/l10n_locales.py check` | Exit 1 |

Pick the section that matches the request.

## Set up

Run this when `l10n.yaml` doesn't exist. `/setup-project` sends you here after
the interview, with the languages already chosen.

1. **Languages.** If they aren't chosen yet, ask once: "Which languages
   besides English?" Suggest `fr es de it nl pt ja` as examples, not a
   default. Accept names or codes and convert names to ISO 639-1 codes
   (`pt_BR` for a region). "None for now" is fine: set up English only, so
   adding a language later is a single command.
2. **Templates.** If `scripts/project_layout.py` is missing, stop: this needs
   `/setup-project` first. Otherwise render the overlay. Leave out `--force`
   so existing files stay as they are:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" --dest . \
     --app-name "<APP_NAME>" --bundle-id "<BUNDLE_ID>" --l10n
   ```

   Take the app name from `CLAUDE.md`'s title and the bundle id from
   `PRODUCT_BUNDLE_IDENTIFIER` in `ios/Runner.xcodeproj/project.pbxproj`.
3. **Dependencies and pubspec.**

   ```bash
   flutter pub add flutter_localizations --sdk=flutter
   flutter pub add intl:any
   python3 scripts/l10n_locales.py setup
   ```

   `setup` sets `flutter: generate: true` and syncs the plist. It exits 1 and
   prints the command if a dependency is still missing.
4. **Languages.** `python3 scripts/l10n_locales.py add <codes…>`, then
   [translate](#translating) every key it prints.
5. **Wire the app.** In the `MaterialApp` (or `.router`, or `CupertinoApp`)
   in `lib/`. The generated `localizationsDelegates` already include the
   Material, Cupertino and Widgets delegates, so don't list them by hand:

   ```dart
   import 'package:<PACKAGE_NAME>/l10n/l10n.dart';

   MaterialApp(
     onGenerateTitle: (context) => context.l10n.appTitle,
     localizationsDelegates: AppLocalizations.localizationsDelegates,
     supportedLocales: AppLocalizations.supportedLocales,
     // ...
   )
   ```

   Remove the hard-coded `title:`. Move any other user-visible strings in the
   starter app into `app_en.arb` (see [Adding or changing a string](#adding-or-changing-a-string)).
6. **Generate and verify.**

   ```bash
   flutter gen-l10n
   flutter analyze
   flutter test test/l10n
   python3 scripts/l10n_locales.py check
   ```

   All four must pass. Commit the generated `lib/l10n/app_localizations*.dart`,
   because CI compares against them.

## Adding a language

```bash
python3 scripts/l10n_locales.py add <code…>
```

The script creates `app_<code>.arb` with the English values copied in, prints
each key, and adds the code to `CFBundleLocalizations`. It never overwrites an
existing ARB. A regional code (`pt_BR`) needs its base (`pt`) too. Then
[translate](#translating) every printed key, run the step 6 checks, and add
the language to any per-locale layout tests the app has.

## Adding or changing a string

One edit set covers every language:

1. Change `app_en.arb`. A new key gets an `@key` block when it has
   placeholders, or when the English alone doesn't give enough context.
2. Make the same change in every other `app_<lang>.arb`, translated. A changed
   English value needs a new translation even though the key is the same.
3. `flutter gen-l10n`, then use `context.l10n.<key>` in the widget.

The hook fires after each ARB edit and lists what still differs. Finish every
language before moving on. Don't leave a locale for later.

Give every placeholder a typed entry in the `@key` block. Without one,
gen-l10n types it `Object` and does no locale formatting:

```json
"greeting": "Hello {name}",
"@greeting": {
  "description": "Home screen header",
  "placeholders": {"name": {"type": "String", "example": "Sam"}}
},
"balance": "Balance: {amount}",
"@balance": {
  "placeholders": {
    "amount": {"type": "double", "format": "simpleCurrency", "optionalParameters": {"decimalDigits": 2}}
  }
},
"lastPlayed": "Last played {date}",
"@lastPlayed": {
  "placeholders": {"date": {"type": "DateTime", "format": "yMMMd"}}
}
```

Numbers (`int`, `double`, `num`) take an `intl` `NumberFormat` name such as
`compact`, `decimalPattern`, `percentPattern` or `simpleCurrency`. `DateTime`
takes a `DateFormat` skeleton such as `yMd`, `yMMMd` or `jm`. For a custom
pattern like `dd/MM`, add `"isCustomDateFormat": "true"`. Let the format
handle separators, currency symbols and date order. Never build those into
the string.

Counts use ICU plurals (`{count, plural, =1{…} other{…}}`), with the branches
right for each language. Never build a plural with `n == 1 ? … : …`.

A choice between fixed values uses `select`:
`{gender, select, male{he} female{she} other{they}}`. The placeholder type is
`String`. Pass an enum's `.name`, never its display text.

Every `plural` and `select` needs an `other` branch, or gen-l10n fails.

## Translating

- Translate the meaning in context, not word for word. Read the `@key`
  `description` and the widget that shows the string.
- Keep every `{placeholder}` and the ICU structure exactly as in English.
  Translate only the text inside the branches. Never translate a `select`
  key (`male`, `other`) or a placeholder name. Plural branches can differ:
  add the categories a language needs (`=0`, `few`, `many`) and keep `other`.
- Keep the casing convention: if English is all caps, so is the translation.
- Leave brand names and the app title as they are.
- Watch the length. If a translation is much longer than the English, look at
  where it's shown and check fixed-width layouts for overflow.
- Say in your summary that these are machine translations, and that a native
  speaker should review them before the app is marketed in that language.

## Audit

Use this for "is l10n in sync?", or before a release:

1. `python3 scripts/l10n_locales.py check`, which reports key, placeholder and
   plist drift.
2. Find values that are identical to English in a non-English ARB. Each one
   is either a brand name (fine) or a missed translation. List them.
3. Find user-visible strings that skip l10n: grep `lib/` for `Text('`,
   `Text("`, `label: '`, `title: '`, `tooltip: '` and `hintText: '`. Leave out
   `lib/l10n/`, logs and dev screens.
4. Confirm the generated Dart is current: run `flutter gen-l10n`, then
   `git status --short lib/l10n`.

Show the results as a table: locale, missing keys, extra keys, placeholder
drift, untranslated values. Put the list of hard-coded strings after it.
Offer to fix whatever the audit found.

## Do not

- Edit the generated `app_localizations*.dart` by hand
- Leave a key in English to make the parity test pass
- Change English without changing every translation in the same edit
- Localize log messages, analytics values, or persisted enum names
