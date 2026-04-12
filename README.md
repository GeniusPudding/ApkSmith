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

### 1. Install

```bash
git clone https://github.com/GeniusPudding/ApkSmith.git
cd ApkSmith
pip install -e .
```

### 2. Check your environment

```bash
apksmith doctor
```

This prints a table showing which tools are installed and which are
missing. You need all of these on `PATH`:

| Tool | What it does | Where to get it |
|---|---|---|
| Python >= 3.11 | Runs ApkSmith | python.org / pyenv |
| Java >= 11 | Runs apktool & apksigner | adoptium.net |
| `adb` | Talks to your phone | Android SDK platform-tools |
| `apktool` | Decompiles & repacks APKs | https://apktool.org |
| `zipalign` | Aligns the APK for Android | Android SDK build-tools |
| `apksigner` | Signs the APK | Android SDK build-tools |

### 3. Generate a signing key (one time)

Android requires every APK to be signed. Since you don't have the
original developer's key, you sign with your own:

```bash
./scripts/gen_dev_keystore.sh
```

This creates `dev.keystore` with password `changeit`. You only need
to do this once.

### 4. Connect your phone

Connect your Android device via USB and enable USB debugging in
Developer Options. Verify the connection:

```bash
adb devices
```

You should see your device listed. If you have multiple devices,
note the serial number — you'll need it with `-d`.

### 5. Pull the app

```bash
apksmith pull com.example.app -o ./pulled
```

This copies the APK from your phone to `./pulled/`. If the app uses
split APKs (common for Play Store apps), all splits are pulled.

### 6. Instrument (modify) the APK

```bash
apksmith instrument ./pulled/com.example.app_base.apk \
    -o ./out \
    --keystore dev.keystore \
    --keystore-pass changeit
```

This decompiles the APK, applies the `trace_logger` pass (which
injects logging into every method), repacks it, and signs it. The
output is `./out/repacked_com.example.app_base.apk`.

### 7. Install the modded APK

```bash
apksmith install ./out/repacked_com.example.app_base.apk
```

This uninstalls the original app and installs your modified version.

**Important:** because the APK is signed with your key (not the
original developer's), Android treats it as a different app. The old
version must be uninstalled first, which **erases the app's data**
(logins, settings, etc.). This is an Android security restriction,
not an ApkSmith limitation.

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

**Tip:** don't know the package name? Run:
```bash
adb shell pm list packages | grep <keyword>
```

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
- [ ] v0.3: `api_hook` pass (redirect any invoke to your stub)
- [ ] v0.4: `const_patcher` pass (rewrite constants in place)
- [ ] v0.5: `apksmith setup` (auto-download tools)
- [ ] v0.6: plugin system for community-contributed passes
- [ ] v1.0: stable API, tutorial for writing custom passes

## Origin

ApkSmith began as the smali instrumentation engine inside
[SADroid](https://github.com/GeniusPudding/SADroid), a static-aided
dynamic analysis tool for Android. It was extracted so anyone can mod
Android apps at the bytecode level.

## License

[Apache-2.0](LICENSE) — you keep your rights, contributors grant a
patent licence, and anyone can build on top of ApkSmith.
