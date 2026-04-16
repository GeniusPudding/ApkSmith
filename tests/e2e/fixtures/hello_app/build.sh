#!/usr/bin/env bash
# Build the hello_app test fixture APK from source using Android SDK
# build-tools directly (no Gradle needed).
#
# Requires on PATH or via env:
#   - javac (JDK 11+)
#   - aapt2, d8, zipalign, apksigner (Android SDK build-tools)
#   - keytool (JDK)
#   - $ANDROID_HOME pointing to your Android SDK install
#
# Output:
#   tests/e2e/fixtures/hello_app.apk   (the built & signed fixture)
#   tests/e2e/fixtures/debug.keystore  (generated once, reused)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

: "${ANDROID_HOME:?Set ANDROID_HOME to your Android SDK directory}"

# Pick the highest installed platform and build-tools unless overridden.
PLATFORM_DIR="${ANDROID_PLATFORM_DIR:-$(ls -d "$ANDROID_HOME"/platforms/android-* 2>/dev/null | sort -V | tail -n 1)}"
BUILD_TOOLS="${ANDROID_BUILD_TOOLS:-$(ls -d "$ANDROID_HOME"/build-tools/* 2>/dev/null | sort -V | tail -n 1)}"

: "${PLATFORM_DIR:?Could not find any android-XX platform in $ANDROID_HOME/platforms}"
: "${BUILD_TOOLS:?Could not find any build-tools version in $ANDROID_HOME/build-tools}"

ANDROID_JAR="$PLATFORM_DIR/android.jar"

echo "Using platform:    $PLATFORM_DIR"
echo "Using build-tools: $BUILD_TOOLS"
echo ""

BUILD="$SCRIPT_DIR/build"
rm -rf "$BUILD"
mkdir -p "$BUILD/classes" "$BUILD/dex"

# 1. Compile Java sources to .class
echo "[1/6] javac"
javac -source 11 -target 11 \
    -bootclasspath "$ANDROID_JAR" \
    -d "$BUILD/classes" \
    "$SCRIPT_DIR/src/main/java/com/apksmith/test/"*.java

# 2. Convert .class -> classes.dex
echo "[2/6] d8"
"$BUILD_TOOLS/d8" \
    --lib "$ANDROID_JAR" \
    --output "$BUILD/dex" \
    $(find "$BUILD/classes" -name "*.class")

# 3. aapt2 link to produce an APK with manifest (no resources for this minimal app)
echo "[3/6] aapt2 link"
"$BUILD_TOOLS/aapt2" link \
    -I "$ANDROID_JAR" \
    --manifest "$SCRIPT_DIR/AndroidManifest.xml" \
    --min-sdk-version 21 \
    --target-sdk-version 34 \
    -o "$BUILD/base.apk"

# 4. Add classes.dex into the APK
echo "[4/6] inject classes.dex"
cp "$BUILD/dex/classes.dex" "$BUILD/"
( cd "$BUILD" && zip -j base.apk classes.dex )

# 5. zipalign
echo "[5/6] zipalign"
"$BUILD_TOOLS/zipalign" -f 4 "$BUILD/base.apk" "$BUILD/aligned.apk"

# 6. Sign (generate debug keystore if missing)
KEYSTORE="$FIXTURE_DIR/debug.keystore"
if [[ ! -f "$KEYSTORE" ]]; then
    echo "Generating debug.keystore (one-time)"
    keytool -genkeypair -v \
        -keystore "$KEYSTORE" \
        -storepass changeit -keypass changeit \
        -alias hellokey -keyalg RSA -keysize 2048 -validity 10000 \
        -dname "CN=ApkSmith Test, O=Test, C=XX" 2>&1 | tail -3
fi

echo "[6/6] apksigner"
"$BUILD_TOOLS/apksigner" sign \
    --ks "$KEYSTORE" \
    --ks-pass pass:changeit \
    --key-pass pass:changeit \
    --ks-key-alias hellokey \
    --out "$FIXTURE_DIR/hello_app.apk" \
    "$BUILD/aligned.apk"

echo ""
echo "Built: $FIXTURE_DIR/hello_app.apk"
ls -lh "$FIXTURE_DIR/hello_app.apk"
