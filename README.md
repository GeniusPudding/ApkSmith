# ApkSmith

> Mod any Android app without its source code.

ApkSmith lets you pull an app off your Android phone, rewrite its
bytecode however you want, and install it back — all from the command
line. Think of it as a workbench for Android app modding: you bring
the idea, ApkSmith handles the toolchain.

## Full workflow

```
  Your phone                    Your computer                   Your phone
 ┌──────────┐    apksmith pull   ┌──────────────────┐   apksmith install  ┌──────────┐
 │ original  │ ───────────────→  │ decompile        │ ──────────────────→ │ modded   │
 │ app       │    (adb pull)     │ rewrite smali    │    (adb install)    │ app      │
 └──────────┘                    │ repack & sign    │                     └──────────┘
                                 └──────────────────┘
                                  apksmith instrument
```

## Quick start

### 1. One-line setup

Clone the repo and run the setup script. It downloads JDK, Android
SDK, apktool, generates a signing key, and pip-installs ApkSmith —
everything in one command.

**Windows (PowerShell):**
```powershell
git clone https://github.com/GeniusPudding/ApkSmith.git
cd ApkSmith
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
# With emulator for E2E testing:
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -WithEmulator
# Custom install path (default: D:\android):
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Root E:\android
```

**Linux / macOS / WSL:**
```bash
git clone https://github.com/GeniusPudding/ApkSmith.git
cd ApkSmith
bash scripts/setup.sh
# With emulator:
bash scripts/setup.sh --with-emulator
# Custom install path (default: ~/android):
bash scripts/setup.sh --root /opt/android
```

The setup script installs everything to an isolated directory (not
your system paths), prints a verification table at the end, and
creates an `env` script to reload in future sessions:

```bash
# Windows: . D:\android\env.ps1
# Linux:   source ~/android/env.sh
```

### 2. Connect a device or start an emulator

**Real phone:** connect via USB, enable USB debugging in Developer Options.

**Emulator** (if you ran setup with `--with-emulator` / `-WithEmulator`):
```bash
emulator -avd apksmith-test
```

Verify connection:
```bash
adb devices
# Should show your device/emulator as "device"
```

### 3. Pull an app from the device

```bash
apksmith pull com.example.app -o ./pulled
```

Don't know the package name?
```bash
adb shell pm list packages | grep <keyword>
```

### 4. Instrument (modify) the APK

```bash
apksmith instrument ./pulled/com.example.app_base.apk \
    -o ./out \
    --keystore dev.keystore \
    --keystore-pass changeit
```

Output files:
```
./out/
├── com.example.app_base/         ← apktool decompiled directory
│   └── smali/                    ← rewritten smali files are here
│       ├── ApkSmith/
│       │   └── InlineLogs.smali  ← injected helper class
│       └── com/example/app/
│           └── *.smali           ← your app's modified bytecode
└── repacked_com.example.app_base.apk  ← the final signed APK
```

### 5. Install the modded APK

```bash
apksmith install ./out/repacked_com.example.app_base.apk
```

### 6. Verify the logs

```bash
adb logcat ApkSmith:D *:S
```

You should see lines like:
```
D/ApkSmith: [apphash], [Method START], [abc12345] $(7741)
D/ApkSmith: [apphash], [Branch: if-eqz v1, :cond_0 - (line 48)], [abc12345] $(7741)
D/ApkSmith: [apphash], [Method END], [abc12345] $(7741)
```

**Important:** the old version is auto-uninstalled because signatures
differ. This **erases the app's data** (logins, settings). This is an
Android restriction, not an ApkSmith limitation.

## Running the tests

```bash
# Unit tests (no device needed, runs anywhere)
pytest tests/ -v

# E2E test (requires setup + running emulator)
# 1. Build test fixture APK (one time)
bash tests/e2e/fixtures/hello_app/build.sh

# 2. Start emulator if not running
emulator -avd apksmith-test &

# 3. Run E2E
pytest tests/e2e/ -v -s
```

E2E auto-skips with a clear message when prerequisites are missing,
so `pytest tests/` is always safe to run on any machine.

## Commands reference

### `apksmith doctor`

Check that all prerequisite tools are installed.

```
$ apksmith doctor

  Tool           Version                  Status     Note
  ----           -------                  ------     ----
  Python         3.12.7                   ✓          required
  Java           17.0.2                   ✓          required
  apktool        2.9.3                    ✓          required
  zipalign       34.0.0                   ✓          required
  apksigner      34.0.0                   ✓          required
  adb            34.0.5                   ✓          required
  keytool        17.0.2                   ✓          optional
  emulator       (not found)              -          optional

  Devices      1 connected: emulator-5554
```

No device connection needed. Exit code 0 if all required tools are
found, 1 if something is missing.

### `apksmith pull <package> [-o dir] [-d serial]`

Pull an installed app from a connected device.

| Flag | What it does |
|---|---|
| `<package>` | Android package name, e.g. `com.example.app` |
| `-o`, `--output-dir` | Where to save the APK (default: current dir) |
| `-d`, `--device` | Device serial — required if multiple devices are connected |

**Requires:** adb, a connected device.

### `apksmith instrument <apk> -o <dir> --keystore <ks> --keystore-pass <pw>`

Decompile, rewrite, repack, and sign an APK.

| Flag | What it does |
|---|---|
| `<apk>` | Input APK file |
| `-o`, `--output-dir` | Output directory (created if missing) |
| `--keystore` | Path to your `.keystore` file |
| `--keystore-pass` | Keystore password |
| `--key-alias` | Key alias (optional if keystore has one key) |
| `--key-pass` | Key password (defaults to keystore password) |
| `--log-tag` | Logcat tag for injected logs (default: `ApkSmith`) |
| `--target-api-graph` | JSON file defining which API calls to highlight |
| `--pass` | Transform pass to apply (repeatable) |

**Requires:** apktool, zipalign, apksigner. No device needed.

### `apksmith install <apk> [-d serial] [--no-uninstall]`

Install a (repacked) APK onto a connected device.

| Flag | What it does |
|---|---|
| `<apk>` | APK file(s) to install |
| `-d`, `--device` | Device serial |
| `--no-uninstall` | Don't auto-uninstall the old version (will fail if signatures differ) |

**Requires:** adb, a connected device.

## Python API

Everything the CLI does is also available as a Python library:

```python
from pathlib import Path
from apksmith import instrument_apk, InstrumentConfig
from apksmith.toolchain.adb import pull_apk, install_apk

# Pull
apks = pull_apk("com.example.app", Path("./pulled"))

# Instrument
result = instrument_apk(
    apk_path=apks[0],
    output_dir=Path("./out"),
    config=InstrumentConfig(
        keystore=Path("dev.keystore"),
        keystore_pass="changeit",
        on_method=lambda h, sign: print(f"patched {sign}"),
    ),
)

# Install
install_apk(result.repacked_apk)
```

| Export | What it does |
|---|---|
| `instrument_apk()` | Full decompile/rewrite/repack/sign pipeline |
| `InstrumentConfig` | All knobs: tool paths, keystore, log tag, callbacks |
| `InstrumentResult` | Result: repacked APK path, app hash, method map, stats |
| `pull_apk()` | Pull APK(s) from a connected device |
| `install_apk()` | Install APK(s) to a device |
| `list_devices()` | List connected adb devices |
| `apksmith.passes.*` | Individual rewriting passes |

## What can you do with it?

- **Inject tracing / logging** — log every method entry & exit, every
  branch, every sensitive API call. Useful for reverse engineering or
  understanding how an app works.
- **Hook or redirect API calls** — intercept calls to any method and
  reroute them to your own stub.
- **Patch constants and logic** — change a string, flip a boolean, swap
  a URL, remove a check.
- **Add new features** — splice new smali classes and methods into an
  app without its source code.

## Writing your own pass

A pass is a function that takes a list of smali lines and returns the
rewritten text. See `src/apksmith/passes/trace_logger.py` for a full
example. The pipeline handles everything else.

## Roadmap

- [x] v0.1: `trace_logger` pass + decompile/repack/sign toolchain
- [x] v0.2: `pull` / `install` commands + `doctor` diagnostics
- [x] v0.3: E2E test harness with emulator verification
- [ ] v0.4: `api_hook` pass (redirect any invoke to your stub)
- [ ] v0.5: `const_patcher` pass (rewrite constants in place)
- [ ] v0.6: `apksmith setup` (auto-download all tools)
- [ ] v0.7: plugin system for community-contributed passes
- [ ] v1.0: stable API, tutorial for writing custom passes

## Origin

ApkSmith began as the smali instrumentation engine inside
[SADroid](https://github.com/GeniusPudding/SADroid), a static-aided
dynamic analysis tool for Android. It was extracted so anyone can mod
Android apps at the bytecode level.

## License

[Apache-2.0](LICENSE) — you keep your rights, contributors grant a
patent licence, and anyone can build on top of ApkSmith.
