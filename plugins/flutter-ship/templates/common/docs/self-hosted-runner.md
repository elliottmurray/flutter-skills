# Self-hosted runner

iOS integration tests can run on a local Mac instead of `macos-latest`.
Use `/self-hosted-runner`: `config.sh`, a per-user **LaunchAgent** in the
GUI session, `pmset`, then swap `runs-on` in `integration_tests.yml`.

Do not install the runner with `./svc.sh` — that has no WindowServer, and
Simulator boots fail.
