# App Check

Firebase App Check (DeviceCheck / App Attest on iOS, debug tokens locally).
Use `/app-check` to activate the client, register debug tokens, and only
then turn on backend `FIREBASE_APP_CHECK_ENABLED`.

`DISABLE_FIREBASE_APP_CHECK` is a dart-define, not a Remote Config flag:
App Check gates the RC fetch.
