# ApkSmith one-line setup for Windows
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#
# Or if already in PowerShell:
#   .\scripts\setup.ps1
#
# What it does:
#   1. Downloads portable JDK 17 (Temurin)
#   2. Downloads Android cmdline-tools
#   3. Installs SDK components (platform-tools, build-tools, platforms)
#   4. Optionally installs emulator + system image for E2E testing
#   5. Downloads apktool
#   6. Generates a dev keystore for signing
#   7. Creates env.ps1 to reload PATH in future sessions
#   8. pip installs ApkSmith in editable mode
#   9. Runs `apksmith doctor` to verify everything
#
# Default install root: D:\android (change with -Root C:\somewhere)

param(
    [string]$Root = "D:\android",
    [switch]$WithEmulator,
    [switch]$SkipPython
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # speeds up Invoke-WebRequest

$SDK      = "$Root\sdk"
$JDK      = "$Root\jdk-17"
$APKTOOL  = "$Root\apktool"
$AVD_HOME = "$Root\avd"

Write-Host ""
Write-Host "=== ApkSmith Setup ===" -ForegroundColor Cyan
Write-Host "Install root: $Root"
Write-Host ""

# ── helpers ──────────────────────────────────────────────────────────
function Download($url, $dest, $label) {
    if (Test-Path $dest) {
        Write-Host "  [skip] $label already exists"
        return
    }
    Write-Host "  [download] $label ..."
    Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
}

function EnsureDir($path) {
    if (-not (Test-Path $path)) { New-Item -ItemType Directory -Force $path | Out-Null }
}

# ── 1. JDK 17 ───────────────────────────────────────────────────────
Write-Host "[1/8] JDK 17 (Temurin)" -ForegroundColor Yellow
EnsureDir $Root
$jdkZip = "$Root\jdk.zip"
if (-not (Test-Path "$JDK\bin\java.exe")) {
    Download "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13%2B11/OpenJDK17U-jdk_x64_windows_hotspot_17.0.13_11.zip" $jdkZip "JDK 17"
    Write-Host "  [extract] ..."
    Expand-Archive $jdkZip -DestinationPath $Root -Force
    $extracted = Get-ChildItem $Root -Directory | Where-Object { $_.Name -like "jdk-17.*" } | Select-Object -First 1
    if ($extracted -and $extracted.FullName -ne $JDK) {
        if (Test-Path $JDK) { Remove-Item $JDK -Recurse -Force }
        Rename-Item $extracted.FullName $JDK
    }
    Remove-Item $jdkZip -ErrorAction SilentlyContinue
}
Write-Host "  [ok] $( & "$JDK\bin\java.exe" -version 2>&1 | Select-Object -First 1 )"

# ── 2. Android cmdline-tools ────────────────────────────────────────
Write-Host "[2/8] Android cmdline-tools" -ForegroundColor Yellow
$cltDir = "$SDK\cmdline-tools\latest"
if (-not (Test-Path "$cltDir\bin\sdkmanager.bat")) {
    EnsureDir "$SDK\cmdline-tools"
    $cltZip = "$Root\clt.zip"
    Download "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip" $cltZip "cmdline-tools"
    Write-Host "  [extract] ..."
    Expand-Archive $cltZip -DestinationPath "$SDK\cmdline-tools" -Force
    if (Test-Path "$SDK\cmdline-tools\cmdline-tools") {
        if (Test-Path $cltDir) { Remove-Item $cltDir -Recurse -Force }
        Rename-Item "$SDK\cmdline-tools\cmdline-tools" $cltDir
    }
    Remove-Item $cltZip -ErrorAction SilentlyContinue
}
Write-Host "  [ok] sdkmanager $( & "$cltDir\bin\sdkmanager.bat" --version 2>&1 )"

# ── 3. SDK components ───────────────────────────────────────────────
Write-Host "[3/8] SDK components (platform-tools, build-tools, platforms)" -ForegroundColor Yellow
$env:JAVA_HOME = $JDK
echo "y" | & "$cltDir\bin\sdkmanager.bat" --sdk_root="$SDK" "platform-tools" "build-tools;34.0.0" "platforms;android-34" 2>&1 | Select-String "done|Installed" | ForEach-Object { Write-Host "  $_" }
Write-Host "  [ok]"

# ── 4. Emulator (optional) ──────────────────────────────────────────
if ($WithEmulator) {
    Write-Host "[4/8] Emulator + system image (this may take a while)" -ForegroundColor Yellow
    EnsureDir $AVD_HOME
    echo "y" | & "$cltDir\bin\sdkmanager.bat" --sdk_root="$SDK" "emulator" "system-images;android-34;google_apis;x86_64" 2>&1 | Select-String "done|Installed" | ForEach-Object { Write-Host "  $_" }

    # Create AVD if it doesn't exist
    $avdList = & "$cltDir\bin\avdmanager.bat" list avd 2>&1
    if ($avdList -notmatch "apksmith-test") {
        Write-Host "  [create] AVD apksmith-test ..."
        $env:ANDROID_AVD_HOME = $AVD_HOME
        echo "no" | & "$cltDir\bin\avdmanager.bat" create avd -n apksmith-test -k "system-images;android-34;google_apis;x86_64" --device pixel_6 --force 2>&1 | Out-Null
    }
    Write-Host "  [ok] AVD ready. Start with: emulator -avd apksmith-test"
} else {
    Write-Host "[4/8] Emulator skipped (use -WithEmulator to install)" -ForegroundColor DarkGray
}

# ── 5. Apktool ──────────────────────────────────────────────────────
Write-Host "[5/8] Apktool" -ForegroundColor Yellow
EnsureDir $APKTOOL
$apktoolJar = "$APKTOOL\apktool.jar"
if (-not (Test-Path $apktoolJar)) {
    Download "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.10.0.jar" $apktoolJar "apktool 2.10.0"
}
$wrapperBat = "$APKTOOL\apktool.bat"
@"
@echo off
setlocal
set JAVA_HOME=$JDK
"%JAVA_HOME%\bin\java.exe" -jar "%~dp0apktool.jar" %*
"@ | Out-File -Encoding ascii $wrapperBat
Write-Host "  [ok] apktool $( & $wrapperBat --version 2>&1 )"

# ── 6. Dev keystore ────────────────────────────────────────────────
Write-Host "[6/8] Dev keystore" -ForegroundColor Yellow
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $repoRoot) { $repoRoot = (Get-Location).Path }
$ks = Join-Path $repoRoot "dev.keystore"
if (-not (Test-Path $ks)) {
    & "$JDK\bin\keytool.exe" -genkeypair -v `
        -keystore $ks -storepass changeit -keypass changeit `
        -alias apksmith -keyalg RSA -keysize 2048 -validity 10000 `
        -dname "CN=ApkSmith, O=Research, C=XX" 2>&1 | Out-Null
    Write-Host "  [ok] created $ks"
} else {
    Write-Host "  [skip] $ks already exists"
}

# ── 7. env.ps1 ──────────────────────────────────────────────────────
Write-Host "[7/8] Writing env.ps1" -ForegroundColor Yellow
$envScript = "$Root\env.ps1"
@"
# Source this to activate the ApkSmith Android toolchain:
#   . $Root\env.ps1
`$env:JAVA_HOME        = "$JDK"
`$env:ANDROID_HOME     = "$SDK"
`$env:ANDROID_SDK_ROOT = "$SDK"
`$env:ANDROID_AVD_HOME = "$AVD_HOME"
`$env:PATH = @(
    "$JDK\bin",
    "$SDK\cmdline-tools\latest\bin",
    "$SDK\platform-tools",
    "$SDK\build-tools\34.0.0",
    "$SDK\emulator",
    "$APKTOOL",
    `$env:PATH
) -join ";"
Write-Host "Android toolchain activated ($Root)."
"@ | Out-File -Encoding utf8 $envScript
Write-Host "  [ok] Reload later with:  . $envScript"

# ── 8. pip install ──────────────────────────────────────────────────
Write-Host "[8/8] pip install -e ." -ForegroundColor Yellow
if (-not $SkipPython) {
    # Activate env for this session first
    . $envScript
    Push-Location $repoRoot
    pip install -e ".[dev]" 2>&1 | Select-Object -Last 3
    Pop-Location
} else {
    Write-Host "  [skip] -SkipPython"
}

# ── verify ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Verification ===" -ForegroundColor Cyan
. $envScript
apksmith doctor

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host "Reload in a new session:  . $envScript"
if ($WithEmulator) {
    Write-Host "Start emulator:           emulator -avd apksmith-test"
}
Write-Host "Run tests:                pytest tests/ -v"
Write-Host ""
