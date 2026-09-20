# Getting started

Empty directory to a Flutter app calling its own API on the simulator. No
Apple Developer Program account, no Firebase project, no CI secrets. Those
come later and each has its own skill.

Budget 20 minutes, most of it `flutter create` and `uv sync`.

You need macOS with full Xcode, the Flutter SDK, `uv`, and `gh` authenticated.
See [Requirements](../README.md#requirements). The paid Apple membership listed
there is for shipping, not for this walkthrough.

## 1. Install the plugin

```text
/plugin marketplace add elliottmurray/flutter-skills
/plugin install flutter-ship@flutter-skills
```

## 2. Run `/setup-project`

```bash
mkdir hello-ship && cd hello-ship && git init
```

Then `/setup-project`. It interviews you one question at a time. For this
walkthrough:

| Question | Answer |
|---|---|
| App name / bundle id | `Hello Ship` / `com.example.helloship` |
| Firebase? | **no** (section 7 covers adding it) |
| Backend | **FastAPI** |
| iOS release CI now? | later |
| Self-hosted runner now? | later |

Git has to be initialized first. `render.py` installs the pre-commit hook into
`.git/hooks/`, and skips it silently when there is no `.git`.

What you get: the Flutter app at the repo root, `backend/` with a FastAPI
service, four GitHub Actions workflows, `analysis_options.yaml`, an
`integration_test/` harness, and a complexity baseline.

Check the Flutter half works before touching the API:

```bash
flutter test
flutter analyze
```

## 3. Start the backend

`/setup-project` drops a thin `backend/`. `/fastapi-setup` fills it out, or do
it by hand:

```bash
cd backend
cp sample.env .env
uv sync --group dev
uv run pytest -q
uv run uvicorn main:app --reload --port 8000
```

In another shell:

```bash
curl -s localhost:8000/health
# {"status":"ok"}
```

`sample.env` sets `FIREBASE_APP_CHECK_ENABLED=false`, so the service never
touches Firebase. That is the whole reason this step needs no credentials.
Section 7 explains what changes when you flip it.

## 4. Add the hello endpoint

The template ships `/health` and nothing else. Add a route to `backend/main.py`:

```python
@app.get("/hello")
async def hello(_app_check: None = Depends(verify_app_check)) -> dict[str, str]:
    return {"message": "Hello from the API"}
```

`Depends(verify_app_check)` is the point. With enforcement off the dependency
returns immediately, so this is a plain public route today. Turn enforcement on
later and the same line starts rejecting requests without a valid token. You do
not rewrite the route to secure it.

A test in `backend/tests/test_hello.py`:

```python
from fastapi.testclient import TestClient

from main import app


def test_hello():
    response = TestClient(app).get("/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from the API"}
```

```bash
uv run pytest -q
uv run ruff check .
```

## 5. Call it from Flutter

```bash
cd ..
flutter pub add http
```

Put the call behind a class that takes its `http.Client`, so the test does not
need a live server. `lib/api/hello_client.dart`:

```dart
import 'dart:convert';

import 'package:http/http.dart' as http;

/// Base URL of the API. Defaults to the local uvicorn port; override with
/// `--dart-define=API_BASE_URL=https://...` for a deployed backend.
const kApiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000',
);

class HelloClient {
  HelloClient({http.Client? client, this.baseUrl = kApiBaseUrl})
      : _client = client ?? http.Client();

  final http.Client _client;
  final String baseUrl;

  Future<String> fetchGreeting() async {
    final response = await _client.get(Uri.parse('$baseUrl/hello'));
    if (response.statusCode != 200) {
      throw HelloApiException('API returned ${response.statusCode}');
    }
    return (jsonDecode(response.body) as Map<String, dynamic>)['message']
        as String;
  }
}

class HelloApiException implements Exception {
  HelloApiException(this.message);
  final String message;

  @override
  String toString() => message;
}
```

`test/api/hello_client_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:hello_ship/api/hello_client.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('returns the message field', () async {
    final client = HelloClient(
      client: MockClient((_) async => http.Response('{"message":"hi"}', 200)),
    );

    expect(await client.fetchGreeting(), 'hi');
  });

  test('throws on a non-200', () async {
    final client = HelloClient(
      client: MockClient((_) async => http.Response('nope', 500)),
    );

    expect(client.fetchGreeting(), throwsA(isA<HelloApiException>()));
  });
}
```

The import is `package:hello_ship/...` — your package name, which is the app
name lowercased with non-alphanumerics replaced by `_`.

Now show it. Replace the body of the `flutter create` counter app in
`lib/main.dart`:

```dart
import 'package:flutter/material.dart';

import 'api/hello_client.dart';

void main() => runApp(const HelloApp());

class HelloApp extends StatelessWidget {
  const HelloApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        appBar: AppBar(title: const Text('Hello Ship')),
        body: const Center(child: GreetingText()),
      ),
    );
  }
}

class GreetingText extends StatefulWidget {
  const GreetingText({super.key});

  @override
  State<GreetingText> createState() => _GreetingTextState();
}

class _GreetingTextState extends State<GreetingText> {
  late final Future<String> _greeting = HelloClient().fetchGreeting();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<String>(
      future: _greeting,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const CircularProgressIndicator();
        }
        if (snapshot.hasError) {
          return Text('Failed: ${snapshot.error}');
        }
        return Text(snapshot.data ?? '', key: const Key('greeting'));
      },
    );
  }
}
```

The future is created in the field initializer, not in `build`. A
`FutureBuilder` fed `HelloClient().fetchGreeting()` inline re-runs the request
on every rebuild, which `/architecture` flags. The `Key('greeting')` is there
so an integration test can find the text later.

## 6. Run it

Leave uvicorn running. In the app directory:

```bash
open -a Simulator
flutter run
```

"Hello from the API" on a white screen means the whole path works: Flutter on
the simulator, over the host loopback, into uvicorn, through the App Check
dependency that is currently a no-op, and back.

The iOS Simulator shares the host network stack, so `localhost:8000` is the
uvicorn you started. An Android emulator would need `10.0.2.2`, but
`/setup-project` runs `flutter create --platforms=ios`.

If the request fails with a cleartext or ATS error, add this to
`ios/Runner/Info.plist` and restart the app:

```xml
<key>NSAppTransportSecurity</key>
<dict>
  <key>NSAllowsLocalNetworking</key>
  <true/>
</dict>
```

That key covers loopback and `.local` only, so it does not open up arbitrary
HTTP the way `NSAllowsArbitraryLoads` does.

Then run everything the pre-commit hook will run anyway:

```bash
flutter test
flutter analyze
cd backend && uv run pytest -q && uv run ruff check .
```

The first commit that adds `hello_client.dart` moves the complexity baseline.
`/complexity` owns the ratchet; the PostToolUse hook stays quiet until a
sensor exists.

## 7. Where Firebase config goes

Nothing above needed Firebase. Adding it changes both halves, and the two halves
take different credentials. This is the part people get wrong.

### The client

`/firebase-setup` creates the project, registers the iOS app, and downloads
`ios/Runner/GoogleService-Info.plist`. That plist is client config: API key,
project id, sender id. It ships inside the IPA, every user has a copy, and it
grants nothing on its own. `/app-check` then turns on App Attest so that
Firebase can tell your app apart from a script holding the same plist.

### The backend

`backend/main.py` reads one environment variable to decide whether Firebase
exists at all:

```python
APP_CHECK_ENABLED = os.environ.get("FIREBASE_APP_CHECK_ENABLED", "false").lower() == "true"
```

While that is `false`, `_init_firebase()` is never called, `firebase-admin` is
an unused import, and `verify_app_check` returns on its first line. The backend
has no Firebase config because it asks for none.

Set it to `true` and `_init_firebase()` runs at **import time**, not per
request. It looks for credentials in this order:

1. `GOOGLE_APPLICATION_CREDENTIALS` — absolute path to a service account JSON
   file. The project id comes from inside the file.
2. Application Default Credentials, with the project id from
   `GOOGLE_CLOUD_PROJECT`. This is the Cloud Run or GKE path, where the
   metadata server supplies the credential and there is no file to mount.

If neither resolves, the module raises `RuntimeError` and uvicorn refuses to
start. The service fails at boot rather than serving 500s, which is what you
want from a misconfigured auth gate.

The service account JSON is not the plist and not either `.p8`. Get it from
Firebase Console → Project settings → **Service accounts** → Generate new
private key. It is a private key with admin authority over the project. Keep it
outside the repo, point at it with an absolute path, and never commit it:

```bash
# backend/.env — already gitignored via **/.env
FIREBASE_APP_CHECK_ENABLED=true
GOOGLE_APPLICATION_CREDENTIALS=/Users/you/.config/hello-ship/service-account.json
```

Under Docker the path has to exist inside the container, so mount it:

```bash
docker run --rm -p 8000:8000 \
  -e FIREBASE_APP_CHECK_ENABLED=true \
  -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/sa.json \
  -v /Users/you/.config/hello-ship/service-account.json:/run/secrets/sa.json:ro \
  app-api
```

The project id the backend resolves must match the project the app's plist
points at. Two projects, and every token verification fails with an error that
does not say so.

### The four credentials

| File | Lives | Committed | What it does |
|---|---|---|---|
| `GoogleService-Info.plist` | `ios/Runner/` | yes | Tells the app which Firebase project to talk to |
| Service account JSON | outside the repo, path in `GOOGLE_APPLICATION_CREDENTIALS` | never | Lets the backend verify App Check tokens |
| DeviceCheck `.p8` | uploaded to the Firebase console, then delete the download | never | Firebase's App Attest fallback on iOS |
| App Store Connect `.p8` | a GitHub secret, set by `/ios-ci-setup` | never | Uploads builds to TestFlight |

Only the first one goes in git. `/app-check` owns the third, `/ios-ci-setup` the
fourth, and they are different files despite both being `.p8`.

### The header nobody wires for you

`templates/app-check/lib/services/app_check_util.dart` gives you
`activateAppCheck()`, which turns the provider on. It does not attach anything
to your HTTP calls. Once enforcement is on, `HelloClient` has to send the token
itself:

```dart
final token = await FirebaseAppCheck.instance.getToken();
final response = await _client.get(
  Uri.parse('$baseUrl/hello'),
  headers: {if (token?.token case final t?) 'X-Firebase-AppCheck': t},
);
```

`verify_app_check` reads exactly that header name. A missing or bad token is a
401.

Turning enforcement on while working on the simulator needs a debug token, not
App Attest, which cannot run on a simulator. `/app-check` registers one in the
console. Until then `FIREBASE_APP_CHECK_ENABLED=false` locally is the sane
default, and the flag is deliberately absent from `release.yml` so you cannot
bake it into an IPA.

## 8. Where to go next

Roughly in order, each one standalone:

| Skill | What it unblocks |
|---|---|
| `/tdd` | Red-green-refactor for the next feature |
| `/verify` | Drive the running simulator: tap, eval, screenshot |
| `/fastapi-setup` | Docker, App Check on real routes |
| `/firebase-setup` | The project, the iOS app, the `TestFlight` RC condition |
| `/app-check` | App Attest, DeviceCheck, debug tokens, then section 7 |
| `/feature-flags` | Remote Config flags with a beta-only tier |
| `/ios-ci-setup` | Signing secrets. Needs the paid Apple account |
| `/self-hosted-runner` | Move the Mac jobs off `macos-latest` billing |
| `/complexity` | Turn the baseline into a ratchet |

[CATALOG.md](../CATALOG.md) lists what each one needs before it will run.
