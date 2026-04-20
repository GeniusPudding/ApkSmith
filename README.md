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

### 0. Install the Android toolchain

ApkSmith needs Java, the Android SDK tools, and apktool. If you
already have Android Studio installed, most of these are already on
your machine — skip to step 1 and run `apksmith doctor` to check.

If starting from scratch, here's a fully command-line setup (no
Android Studio needed). Adjust paths for your OS.

<details>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
# Pick an install root (any drive, not just C:)
$root = "D:\android"
New-Item -ItemType Directory -Force $root

# 1. Portable JDK 17
Invoke-WebRequest -Uri "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13%2B11/OpenJDK17U-jdk_x64_windows_hotspot_17.0.13_11.zip" -OutFile "$root\jdk.zip"
Expand-Archive "$root\jdk.zip" -DestinationPath $root -Force
Rename-Item (Get-ChildItem $root -Directory "jdk-17.*").FullName "$root\jdk-17"
Remove-Item "$root\jdk.zip"

# 2. Android cmdline-tools
New-Item -ItemType Directory -Force "$root\sdk\cmdline-tools"
Invoke-WebRequest -Uri "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip" -OutFile "$root\clt.zip"
Expand-Archive "$root\clt.zip" -DestinationPath "$root\sdk\cmdline-tools" -Force
Rename-Item "$root\sdk\cmdline-tools\cmdline-tools" "$root\sdk\cmdline-tools\latest"
Remove-Item "$root\clt.zip"

# 3. Set up environment for this session
$env:JAVA_HOME = "$root\jdk-17"
$env:ANDROID_HOME = "$root\sdk"
$env:PATH = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\cmdline-tools\latest\bin;$env:PATH"

# 4. Install SDK components (accept license when prompted)
echo "y" | sdkmanager --sdk_root="$env:ANDROID_HOME" "platform-tools" "build-tools;34.0.0" "platforms;android-34"

# 5. (Optional) Emulator for E2E testing
echo "y" | sdkmanager --sdk_root="$env:ANDROID_HOME" "emulator" "system-images;android-34;google_apis;x86_64"
New-Item -ItemType Directory -Force "$root\avd"
$env:ANDROID_AVD_HOME = "$root\avd"

# 6. Apktool
New-Item -ItemType Directory -Force "$root\apktool"
Invoke-WebRequest -Uri "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.10.0.jar" -OutFile "$root\apktool\apktool.jar"
@"
@echo off
"%~dp0..\jdk-17\bin\java.exe" -jar "%~dp0apktool.jar" %*
"@ | Out-File -Encoding ascii "$root\apktool\apktool.bat"

# 7. Add everything to PATH
$env:PATH = "$root\apktool;$env:ANDROID_HOME\platform-tools;$env:ANDROID_HOME\build-tools\34.0.0;$env:ANDROID_HOME\emulator;$env:PATH"

# Verify
java -version; adb version; apktool --version
```

To reload the environment in a new PowerShell session later:

```powershell
. D:\android\env.ps1
```

</details>

<details>
<summary><strong>Linux / macOS / WSL (bash)</strong></summary>

```bash
ROOT=~/android

# JDK 17 (use your package manager or download from adoptium.net)
# Ubuntu:  sudo apt install openjdk-17-jdk
# macOS:   brew install openjdk@17

# Android cmdline-tools
mkdir -p $ROOT/sdk/cmdline-tools
wget https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O /tmp/clt.zip
unzip /tmp/clt.zip -d $ROOT/sdk/cmdline-tools
mv $ROOT/sdk/cmdline-tools/cmdline-tools $ROOT/sdk/cmdline-tools/latest

export ANDROID_HOME=$ROOT/sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$PATH

yes | sdkmanager "platform-tools" "build-tools;34.0.0" "platforms;android-34"
# Optional: emulator
yes | sdkmanager "emulator" "system-images;android-34;google_apis;x86_64"

# Apktool
mkdir -p $ROOT/apktool
wget https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.10.0.jar -O $ROOT/apktool/apktool.jar
echo '#!/bin/bash' > $ROOT/apktool/apktool
echo 'java -jar "$(dirname "$0")/apktool.jar" "$@"' >> $ROOT/apktool/apktool
chmod +x $ROOT/apktool/apktool

export PATH=$ROOT/apktool:$ANDROID_HOME/platform-tools:$ANDROID_HOME/build-tools/34.0.0:$ANDROID_HOME/emulator:$PATH
```

To reload in a new session: `source ~/android/env.sh`

</details>

### 1. Install ApkSmith

```bash
git clone https://github.com/GeniusPudding/ApkSmith.git
cd ApkSmith
pip install -e .
```

### 2. Check your environment

```bash
apksmith doctor
```

All required tools should show ✓. If anything is missing, see step 0.

### 3. Generate a signing key (one time)

```bash
./scripts/gen_dev_keystore.sh
```

Creates `dev.keystore` with password `changeit`. Only needed once.

### 4. Connect a device or start an emulator

**Real phone:** connect via USB, enable USB debugging in Developer Options.

**Emulator:**
```bash
# Create AVD (one time)
avdmanager create avd -n apksmith-test -k "system-images;android-34;google_apis;x86_64" --device pixel_6

# Start emulator
emulator -avd apksmith-test
```

Verify connection:
```bash
adb devices
# Should show your device/emulator as "device"
```

### 5. Pull an app from the device

```bash
apksmith pull com.example.app -o ./pulled
```

Don't know the package name?
```bash
adb shell pm list packages | grep <keyword>
```

### 6. Instrument (modify) the APK

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

### 7. Install the modded APK

```bash
apksmith install ./out/repacked_com.example.app_base.apk
```

### 8. Verify the logs

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

### Unit tests (no device needed)

```bash
pytest tests/ -v
# 39 passed — runs on any machine, no Android tools required
```

### E2E test (requires emulator + tools)

The E2E test runs the full pipeline against a real emulator:
instrument → install → launch → capture logcat → verify output.

```bash
# 1. Set up environment (see step 0)
# 2. Build the test fixture APK (one time)
cd tests/e2e/fixtures/hello_app
bash build.sh
cd ../../../..

# 3. Make sure emulator is running
adb devices

# 4. Run E2E
pytest tests/e2e/ -v -s
```

When prerequisites are missing, E2E auto-skips with a clear message.

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
