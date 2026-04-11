#!/usr/bin/env bash
# Generate a self-signed debug keystore for ApkSmith.
#
# The resulting keystore is suitable for research and local testing
# ONLY. Do NOT use it to sign apps you plan to publish.

set -euo pipefail

KEYSTORE="${1:-dev.keystore}"
ALIAS="${ALIAS:-apksmith}"
STOREPASS="${STOREPASS:-changeit}"
KEYPASS="${KEYPASS:-$STOREPASS}"
DNAME="${DNAME:-CN=ApkSmith, O=Research, C=XX}"

if [[ -f "$KEYSTORE" ]]; then
    echo "Refusing to overwrite existing keystore: $KEYSTORE" >&2
    exit 1
fi

keytool -genkeypair -v \
    -keystore "$KEYSTORE" \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -alias "$ALIAS" \
    -storepass "$STOREPASS" -keypass "$KEYPASS" \
    -dname "$DNAME"

cat <<EOF

Wrote $KEYSTORE
  alias      : $ALIAS
  storepass  : $STOREPASS
  keypass    : $KEYPASS
  dname      : $DNAME

Use with:
  apksmith instrument foo.apk \\
      -o out/ \\
      --keystore $KEYSTORE \\
      --keystore-pass $STOREPASS \\
      --key-alias $ALIAS
EOF
