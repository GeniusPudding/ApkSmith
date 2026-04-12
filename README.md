# ApkSmith

> Mod any Android app without its source code.

ApkSmith lets you crack open an APK, rewrite its smali bytecode however
you want, and put it back together as an installable, signed APK — all
from a single command or a few lines of Python. Think of it as a
workbench for Android app modding: you bring the idea, ApkSmith handles
the decompile / repack / resign plumbing.

The rewriting itself is done through **transform passes** — small,
composable functions that each do one job (inject logging, hook an API,
patch a constant, splice in a new feature). You can use the built-in
passes, combine them, or write your own.

## What can you do with it?

- **Inject tracing / logging** — automatically log every method
  entry & exit, every branch taken, every sensitive API call. Useful
  for reverse engineering, behaviour analysis, or just understanding
  how an app works under the hood.
- **Hook or redirect API calls** — intercept calls to any method
  (e.g. `Landroid/telephony/TelephonyManager;->getDeviceId()`) and
  reroute them to your own stub that returns whatever you want.
- **Patch constants and logic** — change a `const-string`, flip a
  boolean, swap a URL, remove a license check — any bytecode-level
  tweak you can express in smali.
- **Add entirely new features** — splice new smali classes and
  methods into an existing app. No source code required.

In short: if you can describe the change in smali, ApkSmith can apply
it at scale and hand you back a working APK.

## Pipeline

```mermaid
flowchart LR
    A[original.apk] --> B[apktool d]
    B --> C[walk smali tree]
    C --> D[transform passes]
    D --> E[patch helpers]
    E --> F[apktool b]
    F --> G[zipalign]
    G --> H[apksigner sign]
    H --> I[modded.apk]
    I --> J[adb install]
```

## Prerequisites

ApkSmith is a Python orchestrator around standard Android reverse
engineering tools:

| Tool | Purpose | How to get it |
|---|---|---|
| Python >= 3.11 | Orchestrator | python.org / pyenv |
| Java >= 11 | apktool / apksigner runtime | Temurin / Zulu |
| `apktool` | decompile / repack | https://apktool.org |
| `zipalign` | alignment | Android SDK build-tools |
| `apksigner` | v1/v2/v3 signing | Android SDK build-tools |
| `keytool` | generate a dev keystore (one-time) | JDK |

All binaries must be on `PATH`, or you can pass explicit paths via
`InstrumentConfig`.

## Quickstart

```bash
pip install -e .

# one-time: generate a dev keystore for signing
./scripts/gen_dev_keystore.sh

# instrument an APK (trace_logger pass is the default)
apksmith instrument target.apk \
    --pass trace_logger \
    --keystore dev.keystore \
    --keystore-pass changeit \
    -o out/
```

Programmatic use:

```python
from pathlib import Path
from apksmith import instrument_apk, InstrumentConfig

result = instrument_apk(
    apk_path=Path("target.apk"),
    output_dir=Path("out"),
    config=InstrumentConfig(
        keystore=Path("dev.keystore"),
        keystore_pass="changeit",
        on_method=lambda h, sign: print(f"patched {sign}"),
    ),
)
print(result.repacked_apk)   # out/repacked_target.apk
print(result.stats)           # methods_patched=1234, ...
```

## How it works

1. **Decompile** — `apktool d` extracts the APK into a directory of
   `.smali` files (Dalvik bytecode in human-readable form).
2. **Walk** — ApkSmith traverses every `.smali` file, skipping
   framework / third-party libraries you don't care about.
3. **Transform** — each pass rewrites the smali in place. The
   built-in `trace_logger` pass, for example, injects `Log.d` calls
   at method boundaries, branches, and target API invocations.
4. **Patch helpers** — a small runtime helper class
   (`ApkSmith/InlineLogs.smali`) is copied into the smali tree so the
   injected code has something to call.
5. **Repack & sign** — `apktool b` rebuilds the APK, `zipalign`
   aligns it, and `apksigner` signs it with your keystore.

The result is a fully installable APK with your modifications baked in.

## Public API

ApkSmith is designed to be **zero-assumption**: it never touches a
database, never writes log files behind your back, and never assumes
anything about your storage layer. Everything it produces is either
returned in `InstrumentResult` or delivered via a callback you supply.

| Export | What it does |
|---|---|
| `InstrumentConfig` | All knobs: tool paths, keystore, log tag, skip list, callbacks |
| `InstrumentResult` | Returned by `instrument_apk`: repacked path, app hash, method map, stats |
| `instrument_apk()` | End-to-end pipeline in one call |
| `apksmith.passes.*` | Individual rewriting passes you can compose or replace |

## Roadmap

- [x] v0.1: `trace_logger` pass + full decompile/repack/sign toolchain
- [ ] v0.2: `api_hook` pass (redirect any `invoke-*` to your stub)
- [ ] v0.3: `const_patcher` pass (rewrite constants in place)
- [ ] v0.4: `adb install` integration + device picker
- [ ] v0.5: plugin system for community-contributed passes
- [ ] v1.0: stable public API, tutorial for writing custom passes

## Writing your own pass

A pass is just a function that takes a list of smali lines and returns
the rewritten text. See `src/apksmith/passes/trace_logger.py` for a
full example. The pipeline handles everything else — you only need to
think about smali.

## Origin

ApkSmith began as the smali instrumentation engine inside
[SADroid](https://github.com/GeniusPudding/SADroid), a static-aided
dynamic analysis tool for Android. It was extracted so the same
rewriting engine can serve anyone who wants to mod an Android app at
the bytecode level.

## License

[Apache-2.0](LICENSE) — you keep your rights, contributors grant a
patent licence, and anyone can build on top of ApkSmith (including
commercial tools). Contributions welcome under the same terms.
