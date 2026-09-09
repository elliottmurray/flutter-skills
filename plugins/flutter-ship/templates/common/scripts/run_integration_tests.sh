#!/bin/bash
# Run iOS integration tests on a Simulator (never a physical device).
# Mirrors .github/workflows/integration_tests.yml
#
# Usage (from anywhere):
#   ./scripts/run_integration_tests.sh
#   ./scripts/run_integration_tests.sh integration_test/my_flow_test.dart
#   ./scripts/run_integration_tests.sh --keep-simulator

set -euo pipefail

SCRIPT_START_EPOCH="$(date +%s)"

log() {
  local elapsed=$(( $(date +%s) - SCRIPT_START_EPOCH ))
  printf '[%s] [+%02dm%02ds] %s\n' "$(date '+%H:%M:%S')" "$((elapsed / 60))" "$((elapsed % 60))" "$*"
}

STAGE_START_EPOCH=0
stage_start() {
  STAGE_START_EPOCH="$(date +%s)"
  log "-> $*"
}
stage_end() {
  local duration=$(( $(date +%s) - STAGE_START_EPOCH ))
  log "<- $* (${duration}s)"
}

KEEP_SIMULATOR=false
TEST_TARGET="integration_test/app_test.dart"
for arg in "$@"; do
  case "$arg" in
    --keep-simulator) KEEP_SIMULATOR=true ;;
    -h|--help)
      echo "Usage: $0 [--keep-simulator] [integration_test/foo_test.dart]"
      echo "  Default target: integration_test/app_test.dart"
      exit 0
      ;;
    -*)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
    *)
      TEST_TARGET="$arg"
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

SIMULATOR_UDID="${SIMULATOR_UDID:-}"
CREATED_SIMULATOR=false
SIMULATOR_NAME="local-integration-test"

cleanup() {
  local exit_code=$?
  if [[ $exit_code -eq 0 ]]; then
    log "Script finished successfully."
  else
    log "Script exiting with error (exit code $exit_code)."
  fi

  if [[ "$CREATED_SIMULATOR" != true ]]; then
    return
  fi
  if [[ "$KEEP_SIMULATOR" == true ]]; then
    log "Keeping simulator $SIMULATOR_NAME ($SIMULATOR_UDID)"
    return
  fi
  if [[ -n "$SIMULATOR_UDID" ]]; then
    log "Shutting down simulator $SIMULATOR_UDID"
    xcrun simctl shutdown "$SIMULATOR_UDID" 2>/dev/null || true
    log "Deleting simulator $SIMULATOR_UDID"
    xcrun simctl delete "$SIMULATOR_UDID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

pick_device_type() {
  local preferred
  for preferred in \
    "iPhone 17 Pro" "iPhone 17" "iPhone 16 Pro" "iPhone 16" \
    "iPhone 15 Pro" "iPhone 15" "iPhone 14" "iPhone SE (3rd generation)"; do
    if xcrun simctl list devicetypes | grep -q "$preferred"; then
      echo "$preferred"
      return
    fi
  done
  xcrun simctl list devicetypes available -j \
    | python3 -c "
import sys, json
types = [t for t in json.load(sys.stdin)['devicetypes'] if t['name'].startswith('iPhone')]
if not types:
    raise SystemExit('No available iPhone Simulator device types found')
print(types[-1]['name'])
"
}

latest_ios_runtime() {
  xcrun simctl list runtimes iOS -j \
    | python3 -c "
import sys, json
runtimes = [
    r for r in json.load(sys.stdin)['runtimes']
    if r.get('isAvailable') and r.get('platform') == 'iOS'
]
if not runtimes:
    raise SystemExit('No available iOS Simulator runtimes found')
print(runtimes[-1]['identifier'])
"
}

stage_start "Enabling Swift Package Manager"
flutter config --enable-swift-package-manager
stage_end "Enabling Swift Package Manager"

mkdir -p screenshots logs

prepare_simulator() {
  local udid
  if [[ -z "$SIMULATOR_UDID" ]]; then
    log "Creating simulator"
    local device_type runtime
    device_type="$(pick_device_type)"
    runtime="$(latest_ios_runtime)"
    log "Device: $device_type, runtime: $runtime"
    udid="$(xcrun simctl create "$SIMULATOR_NAME" "$device_type" "$runtime")"
    echo "$udid" > "$SIM_UDID_FILE"
    echo "true" > "$SIM_CREATED_FILE"
  else
    log "Reusing supplied simulator $SIMULATOR_UDID"
    udid="$SIMULATOR_UDID"
    echo "$udid" > "$SIM_UDID_FILE"
    echo "false" > "$SIM_CREATED_FILE"
  fi

  log "Booting simulator $udid"
  xcrun simctl boot "$udid" 2>/dev/null || true
  if [[ "${HEADLESS_SIMULATOR:-}" != "true" ]]; then
    open -a Simulator --args -CurrentDeviceUDID "$udid" 2>/dev/null \
      || open -a Simulator 2>/dev/null \
      || true
  fi
  xcrun simctl bootstatus "$udid"
  log "Simulator $udid ready"
}

SIM_UDID_FILE="$(mktemp)"
SIM_CREATED_FILE="$(mktemp)"

stage_start "Preparing simulator + flutter pub get (parallel)"

prepare_simulator > logs/sim_prepare.log 2>&1 &
SIM_PID=$!

set +e
if [[ "${PUB_CACHE_HIT:-}" == "true" ]]; then
  flutter pub get --offline
else
  flutter pub get
fi
PUB_GET_EXIT_CODE=$?

wait "$SIM_PID"
SIM_EXIT_CODE=$?
set -e

stage_end "Preparing simulator + flutter pub get (parallel)"
cat logs/sim_prepare.log

if [[ "$SIM_EXIT_CODE" -eq 0 ]]; then
  SIMULATOR_UDID="$(cat "$SIM_UDID_FILE")"
  if [[ "$(cat "$SIM_CREATED_FILE")" == "true" ]]; then
    CREATED_SIMULATOR=true
  fi
fi
rm -f "$SIM_UDID_FILE" "$SIM_CREATED_FILE"

if [[ "$PUB_GET_EXIT_CODE" -ne 0 ]]; then
  log "flutter pub get failed (exit $PUB_GET_EXIT_CODE)"
  exit "$PUB_GET_EXIT_CODE"
fi
if [[ "$SIM_EXIT_CODE" -ne 0 ]]; then
  log "Simulator preparation failed (exit $SIM_EXIT_CODE). See sim_prepare log above."
  exit "$SIM_EXIT_CODE"
fi

DRIVE_VERBOSE="${DRIVE_VERBOSE:-0}"
DRIVE_ARGS=(
  --driver=test_driver/integration_test.dart
  --target="$TEST_TARGET"
  --screenshot=screenshots/
  -d "$SIMULATOR_UDID"
)
if [[ "$DRIVE_VERBOSE" == "1" ]]; then
  DRIVE_ARGS+=(--verbose)
fi

stage_start "flutter drive (integration test)"
set +e
flutter drive "${DRIVE_ARGS[@]}" 2>&1 | tee logs/flutter_drive.log
DRIVE_EXIT_CODE=${PIPESTATUS[0]}
set -e
stage_end "flutter drive (integration test)"

if [[ "$DRIVE_EXIT_CODE" -ne 0 ]]; then
  log "flutter drive failed (exit $DRIVE_EXIT_CODE). Full log: logs/flutter_drive.log"
  exit "$DRIVE_EXIT_CODE"
fi

log "Integration tests passed. Screenshots: screenshots/"
