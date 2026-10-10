# Using Chrome with the console skills

Three skills spend most of their time in a web console rather than your repo:

| Skill | Sites |
|---|---|
| `/ios-ci-setup` | `developer.apple.com`, `appstoreconnect.apple.com` |
| `/firebase-setup` | `console.firebase.google.com` |
| `/app-check` | `developer.apple.com`, `console.firebase.google.com` |

None of these consoles has an API you'd want an agent calling unattended, and
Apple's portal has no usable one for certificates at all. So the skills work
the way you would: open the page, click through it, read values off the
screen. With the Claude in Chrome extension connected, Claude does the
clicking in your own Chrome window. Without it, Claude tells you which page to
open and which button to press, and waits for you to say it's done. You get
the same result either way. Chrome only saves you the back-and-forth.

## Setup

You need a Pro, Max, Team or Enterprise plan, with Claude Code signed in via
`/login`. API-key sessions can't use the extension.

1. Install [Claude in Chrome](https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn)
   and sign it in to the same claude.ai account and organization as Claude
   Code.
2. Start Claude Code with `claude --chrome`, or run `/chrome` in a session and
   pick **Enabled by default** so you don't need the flag again. The first
   time, Chrome may need a restart before it sees Claude Code.
3. Run `/chrome` and check it says `Status: Enabled` and `Extension: Installed`.
4. Sign in to the consoles in that Chrome profile before you start:
   developer.apple.com, appstoreconnect.apple.com and
   console.firebase.google.com. Claude uses your existing sessions. It never
   types a password.

Site permissions live in the extension. The first time Claude acts on one of
the sites above you'll get a prompt; allowing it for the session saves you a
prompt per click. If you'd rather allow the three sites up front, do it in the
extension's settings.

Turning Chrome on by default loads the browser tools into every session, which
costs context. If you only use it for these three skills, start those sessions
with `claude --chrome` instead.

## What a run looks like

Take `/ios-ci-setup`:

1. Claude checks the Apple account prerequisites with you and runs the local
   checks (`xcode-select -p`, `gh auth status`, the bundle id).
2. It asks you to finish Apple's two-factor prompt in Chrome and waits until
   you say the session is unlocked.
3. It opens a new tab on Certificates, Identifiers & Profiles and creates or
   finds the App ID. You'll see each page change in your Chrome window.
4. It stops and hands over to you for the distribution certificate. The
   private key has to be made on your Mac by Xcode or Keychain, and no browser
   can do that.
5. Back in Chrome, it creates the provisioning profile and the App Store
   Connect API key, asking you to confirm before each **Create**. The
   `.mobileprovision` and `.p8` download wherever Chrome saves files (usually
   `~/Downloads`). Claude works with them from the shell, and the skill
   suggests moving them somewhere outside the repo, like `~/ios-signing/`.
6. The secrets go to GitHub with `gh secret set` from the terminal, one at a
   time and each with your yes. The browser isn't involved in this step.

`/firebase-setup` and `/app-check` follow the same pattern: you get past
Google's sign-in or account picker, then Claude works the console while you
watch.

## What stays with you

Some steps are yours whether Chrome is connected or not:

- Signing in, 2FA, account pickers and CAPTCHAs. Claude pauses on any login
  page.
- Creating the certificate private key in Xcode or Keychain.
- Uploading key files into a console, such as the DeviceCheck `.p8` that
  `/app-check` gives Firebase. The extension refuses to upload files that look
  like credentials, and you should be the one deciding where a private key
  goes anyway.
- Saying yes to anything that creates or revokes something in a console, and
  to every `gh secret set`.

Claude reads IDs (Team ID, Key ID, Issuer ID) off the page. It doesn't paste
secret values into the chat or a PR body, and the skills tell it to show only
a length and the first and last four characters when confirming a secret.

## When it goes wrong

Consoles change their layouts, and Apple's portal sometimes asks for 2FA again
partway through. The skills treat both the same way: if a click misses or a
challenge appears, Claude stops driving the browser and switches to telling you
what to click. You don't need to restart the skill.

If the browser tools stop responding:

- Check for a JavaScript alert or confirm dialog on the page. Those block the
  extension until you dismiss them by hand.
- Run `/chrome` and pick **Reconnect extension**. The extension goes idle in
  long sessions, and this is the usual fix.
- "Browser extension is not connected" usually means the extension is signed in
  to a different claude.ai organization than Claude Code. `/status` shows which
  one Claude Code is using.

The [Claude Code Chrome docs](https://code.claude.com/docs/en/chrome) cover the
rest of the troubleshooting.

## Without Chrome

Nothing changes in the steps. Claude names the page and the button, waits for
you, and asks you to read back the values it needs, like the profile UUID or
the Key ID. Expect it to take longer and to involve more copying and pasting.
