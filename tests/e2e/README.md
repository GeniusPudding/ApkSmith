# End-to-end tests

The E2E test builds, installs, and verifies a modded APK against a
**real Android emulator or device**. It exists to catch regressions
that unit tests cannot — things like:

- Does the repacked APK actually install on a device?
- Does the app still launch after instrumentation?
- Do the injected `Log.d` calls actually fire at runtime?
- Do the original app's behaviours still work?

Unlike the unit tests, E2E requires a full Android toolchain to be
installed. When any prerequisite is missing the tests auto-skip, so
`pytest` on a bare machine still passes.

## What gets tested

`test_e2e_instrument.py` runs the full pipeline:

1. `apksmith.instrument_apk()` on the `hello_app.apk` fixture.
2. `adb uninstall com.apksmith.test` (cleanup).
3. `adb install -r <repacked apk>`.
4. `adb logcat -c` to clear.
5. `adb shell am start -n com.apksmith.test/.MainActivity`.
6. Wait 3 s, then `adb logcat -d` to drain the buffer.
7. Assert:
   - `ORIGINAL Log.d` calls appear (app not broken)
   - no `FATAL EXCEPTION`
   - at least 3 `[Method START]` / `[Method END]` entries
   - at least 2 `[Branch:]` entries (the fixture has 2 if/else)
   - method hashes in logs map back to `result.methods`

## Prerequisites

| Tool | Purpose | Where to get |
|---|---|---|
| Python 3.11+ + `pip install -e .[dev]` | Runs the test harness | pyproject |
| JDK 11+ (`javac`, `keytool`) | Builds the fixture APK | adoptium.net |
| Android SDK with `build-tools` and a `platforms/android-34` or similar | Compiles/packages/signs the fixture | `sdkmanager` |
| `apktool` on PATH | ApkSmith pipeline | apktool.org |
| `adb` on PATH | Talks to the emulator | SDK platform-tools |
| A running Android emulator (API 24+) **or** a real device | Runs the modded APK | SDK emulator / phone |

Verify everything is reachable with:

```bash
apksmith doctor
```

## One-time setup

### 1. Install Android SDK components (if you don't have them)

```bash
# assumes sdkmanager is already on PATH (from cmdline-tools)
sdkmanager "platform-tools" "build-tools;34.0.0" "platforms;android-34"
sdkmanager "system-images;android-34;google_apis;x86_64"
export ANDROID_HOME=~/Android/Sdk   # or wherever your SDK is
```

### 2. Build the fixture APK

The fixture is a tiny Java app with three methods and two branches.
Build it once:

```bash
cd tests/e2e/fixtures/hello_app
./build.sh
```

This produces:

- `tests/e2e/fixtures/hello_app.apk` — the APK the test consumes
- `tests/e2e/fixtures/debug.keystore` — the signing key (reused on rebuild)

Both are gitignored so they don't end up in commits.

### 3. Start an emulator

```bash
# create a virtual device (one-time)
avdmanager create avd -n apksmith-test -k "system-images;android-34;google_apis;x86_64"

# boot it (in a separate terminal)
emulator -avd apksmith-test
```

Wait until `adb devices` shows the emulator with state `device`.

## Running the E2E test

From the ApkSmith repo root:

```bash
pytest tests/e2e/ -v
```

Expected output when everything is wired up:

```
tests/e2e/test_e2e_instrument.py::test_instrument_install_launch_verify_logs PASSED
```

## Running only unit tests (skip E2E)

The default `pytest` run will auto-skip E2E when prerequisites are
absent, but you can also exclude it explicitly:

```bash
pytest -m "not e2e"
```

## Troubleshooting

**"Fixture APK not built"** — run `tests/e2e/fixtures/hello_app/build.sh`.

**"No Android device or emulator online"** — start an emulator or plug
in a phone with USB debugging enabled, then `adb devices` should show
it as `device` (not `unauthorized` or `offline`).

**"Missing required tools on PATH"** — `apksmith doctor` tells you
which specific tool is missing and where to get it.

**"App crashed after instrumentation"** — check
`adb logcat -d *:E` for the crash stack. Common causes:
  - Signature mismatch: run `adb uninstall com.apksmith.test` first.
  - Verifier rejection: the instrumentation pushed some method into an
    invalid bytecode state (e.g. a 4-bit register overflow for methods
    with `.locals >= 14`). File an issue with the offending APK / method.

**Repacked APK installs but the instrumented logs never appear** —
something is filtering your logcat output. Run
`adb logcat ApkSmithE2E:D *:S` by hand to verify the tag is arriving.
