#!/usr/bin/env bash
# ApkSmith one-line setup for Linux / macOS / WSL
#
# Usage:
#   bash scripts/setup.sh
#   bash scripts/setup.sh --with-emulator
#   bash scripts/setup.sh --root ~/android
#
# What it does:
#   1. Downloads/installs JDK 17 (Temurin) if not present
#   2. Downloads Android cmdline-tools
#   3. Installs SDK components (platform-tools, build-tools, platforms)
#   4. Optionally installs emulator + system image for E2E testing
#   5. Downloads apktool
#   6. Generates a dev keystore for signing
#   7. Creates env.sh to reload PATH in future sessions
#   8. pip installs ApkSmith in editable mode
#   9. Runs `apksmith doctor` to verify everything

set -euo pipefail

# ── parse args ──────────────────────────────────────────────────────
ROOT="${HOME}/android"
WITH_EMULATOR=false
SKIP_PYTHON=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --root)          ROOT="$2"; shift 2 ;;
        --with-emulator) WITH_EMULATOR=true; shift ;;
        --skip-python)   SKIP_PYTHON=true; shift ;;
        *)               echo "Unknown arg: $1"; exit 1 ;;
    esac
done

SDK="$ROOT/sdk"
JDK="$ROOT/jdk-17"
APKTOOL_DIR="$ROOT/apktool"
AVD_HOME="$ROOT/avd"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo ""
echo "=== ApkSmith Setup ==="
echo "Install root: $ROOT"
echo ""

mkdir -p "$ROOT"

# ── detect OS ───────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS" in
    Linux*)  PLATFORM="linux" ;;
    Darwin*) PLATFORM="mac" ;;
    MINGW*|MSYS*|CYGWIN*) PLATFORM="windows" ;;
    *)       echo "Unsupported OS: $OS"; exit 1 ;;
esac

# ── 1. JDK 17 ───────────────────────────────────────────────────────
echo "[1/8] JDK 17"
if [[ -f "$JDK/bin/java" ]] || [[ -f "$JDK/bin/java.exe" ]]; then
    echo "  [skip] already installed"
else
    if command -v java &>/dev/null; then
        JAVA_VER=$(java -version 2>&1 | head -1)
        echo "  [skip] system Java found: $JAVA_VER"
        JDK="$(dirname "$(dirname "$(command -v java)")")"
    else
        echo "  [download] Temurin JDK 17 ..."
        case "$PLATFORM" in
            linux)
                JDK_URL="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13%2B11/OpenJDK17U-jdk_x64_linux_hotspot_17.0.13_11.tar.gz"
                curl -fsSL "$JDK_URL" | tar xzf - -C "$ROOT"
                mv "$ROOT"/jdk-17.* "$JDK" 2>/dev/null || true
                ;;
            mac)
                JDK_URL="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13%2B11/OpenJDK17U-jdk_x64_mac_hotspot_17.0.13_11.tar.gz"
                if [[ "$ARCH" == "arm64" ]]; then
                    JDK_URL="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13%2B11/OpenJDK17U-jdk_aarch64_mac_hotspot_17.0.13_11.tar.gz"
                fi
                curl -fsSL "$JDK_URL" | tar xzf - -C "$ROOT"
                mv "$ROOT"/jdk-17.*/Contents/Home "$JDK" 2>/dev/null || mv "$ROOT"/jdk-17.* "$JDK" 2>/dev/null || true
                ;;
            windows)
                JDK_URL="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13%2B11/OpenJDK17U-jdk_x64_windows_hotspot_17.0.13_11.zip"
                curl -fsSL "$JDK_URL" -o "$ROOT/jdk.zip"
                unzip -qo "$ROOT/jdk.zip" -d "$ROOT"
                mv "$ROOT"/jdk-17.* "$JDK" 2>/dev/null || true
                rm -f "$ROOT/jdk.zip"
                ;;
        esac
    fi
fi
echo "  [ok] $("$JDK/bin/java" -version 2>&1 | head -1)"

# ── 2. Android cmdline-tools ────────────────────────────────────────
echo "[2/8] Android cmdline-tools"
CLT="$SDK/cmdline-tools/latest"
if [[ -f "$CLT/bin/sdkmanager" ]] || [[ -f "$CLT/bin/sdkmanager.bat" ]]; then
    echo "  [skip] already installed"
else
    mkdir -p "$SDK/cmdline-tools"
    case "$PLATFORM" in
        linux)   CLT_URL="https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip" ;;
        mac)     CLT_URL="https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip" ;;
        windows) CLT_URL="https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip" ;;
    esac
    echo "  [download] ..."
    curl -fsSL "$CLT_URL" -o "$ROOT/clt.zip"
    unzip -qo "$ROOT/clt.zip" -d "$SDK/cmdline-tools"
    [[ -d "$SDK/cmdline-tools/cmdline-tools" ]] && mv "$SDK/cmdline-tools/cmdline-tools" "$CLT"
    rm -f "$ROOT/clt.zip"
fi
echo "  [ok]"

# ── 3. SDK components ───────────────────────────────────────────────
echo "[3/8] SDK components"
export JAVA_HOME="$JDK"
SDKMGR="$CLT/bin/sdkmanager"
[[ -f "$SDKMGR.bat" ]] && SDKMGR="$SDKMGR.bat"
yes | "$SDKMGR" --sdk_root="$SDK" "platform-tools" "build-tools;34.0.0" "platforms;android-34" 2>&1 | tail -3
echo "  [ok]"

# ── 4. Emulator (optional) ──────────────────────────────────────────
if $WITH_EMULATOR; then
    echo "[4/8] Emulator + system image"
    mkdir -p "$AVD_HOME"
    yes | "$SDKMGR" --sdk_root="$SDK" "emulator" "system-images;android-34;google_apis;x86_64" 2>&1 | tail -3

    AVDMGR="$CLT/bin/avdmanager"
    [[ -f "$AVDMGR.bat" ]] && AVDMGR="$AVDMGR.bat"
    export ANDROID_AVD_HOME="$AVD_HOME"
    if ! "$AVDMGR" list avd 2>&1 | grep -q "apksmith-test"; then
        echo "  [create] AVD apksmith-test ..."
        echo "no" | "$AVDMGR" create avd -n apksmith-test \
            -k "system-images;android-34;google_apis;x86_64" \
            --device pixel_6 --force 2>&1 | tail -1
    fi
    echo "  [ok] Start with: emulator -avd apksmith-test"
else
    echo "[4/8] Emulator skipped (use --with-emulator to install)"
fi

# ── 5. Apktool ──────────────────────────────────────────────────────
echo "[5/8] Apktool"
mkdir -p "$APKTOOL_DIR"
if [[ ! -f "$APKTOOL_DIR/apktool.jar" ]]; then
    echo "  [download] ..."
    curl -fsSL "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.10.0.jar" \
        -o "$APKTOOL_DIR/apktool.jar"
fi
# Write cross-platform wrapper
cat > "$APKTOOL_DIR/apktool" << 'WRAPPER'
#!/usr/bin/env bash
java -jar "$(dirname "$0")/apktool.jar" "$@"
WRAPPER
chmod +x "$APKTOOL_DIR/apktool"
echo "  [ok]"

# ── 6. Dev keystore ────────────────────────────────────────────────
echo "[6/8] Dev keystore"
KS="$REPO_ROOT/dev.keystore"
if [[ ! -f "$KS" ]]; then
    "$JDK/bin/keytool" -genkeypair -v \
        -keystore "$KS" -storepass changeit -keypass changeit \
        -alias apksmith -keyalg RSA -keysize 2048 -validity 10000 \
        -dname "CN=ApkSmith, O=Research, C=XX" 2>&1 | tail -1
    echo "  [ok] created $KS"
else
    echo "  [skip] already exists"
fi

# ── 7. env.sh ───────────────────────────────────────────────────────
echo "[7/8] Writing env.sh"
cat > "$ROOT/env.sh" << ENVEOF
# source this: . $ROOT/env.sh
export JAVA_HOME="$JDK"
export ANDROID_HOME="$SDK"
export ANDROID_SDK_ROOT="$SDK"
export ANDROID_AVD_HOME="$AVD_HOME"
export PATH="\$JAVA_HOME/bin:\$ANDROID_HOME/cmdline-tools/latest/bin:\$ANDROID_HOME/platform-tools:\$ANDROID_HOME/build-tools/34.0.0:\$ANDROID_HOME/emulator:$APKTOOL_DIR:\$PATH"
echo "Android toolchain activated ($ROOT)."
ENVEOF
echo "  [ok] Reload later with: source $ROOT/env.sh"

# ── 8. pip install ──────────────────────────────────────────────────
echo "[8/8] pip install -e ."
if ! $SKIP_PYTHON; then
    source "$ROOT/env.sh"
    cd "$REPO_ROOT"
    pip install -e ".[dev]" 2>&1 | tail -3
else
    echo "  [skip]"
fi

# ── verify ──────────────────────────────────────────────────────────
echo ""
echo "=== Verification ==="
source "$ROOT/env.sh"
apksmith doctor

echo ""
echo "=== Setup complete ==="
echo "Reload in a new session: source $ROOT/env.sh"
$WITH_EMULATOR && echo "Start emulator:          emulator -avd apksmith-test"
echo "Run tests:               pytest tests/ -v"
echo ""
