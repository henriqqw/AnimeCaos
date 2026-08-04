#!/usr/bin/env bash
# Fetch geckodriver binaries and update sha256 checksums in the Flatpak manifest.
# Run this once before building, or whenever changing geckodriver version.

set -euo pipefail

MANIFEST="com.animecaos.App.yaml"
GECKO_VERSION="v0.36.0"
GECKO_X86_URL="https://github.com/mozilla/geckodriver/releases/download/${GECKO_VERSION}/geckodriver-${GECKO_VERSION}-linux64.tar.gz"
GECKO_AARCH64_URL="https://github.com/mozilla/geckodriver/releases/download/${GECKO_VERSION}/geckodriver-${GECKO_VERSION}-linux-aarch64.tar.gz"

echo "Downloading geckodriver ${GECKO_VERSION} to compute checksums..."

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

curl -L --progress-bar "$GECKO_X86_URL" -o "$TMP/gecko-x86.tar.gz"
curl -L --progress-bar "$GECKO_AARCH64_URL" -o "$TMP/gecko-aarch64.tar.gz"

SHA_X86=$(sha256sum "$TMP/gecko-x86.tar.gz" | cut -d' ' -f1)
SHA_AARCH64=$(sha256sum "$TMP/gecko-aarch64.tar.gz" | cut -d' ' -f1)

echo "x86_64:  $SHA_X86"
echo "aarch64: $SHA_AARCH64"

# Patch the manifest in-place
sed -i "s|GECKO_SHA256_X86_64|$SHA_X86|g" "$MANIFEST"
sed -i "s|GECKO_SHA256_AARCH64|$SHA_AARCH64|g" "$MANIFEST"

echo "Checksums updated in $MANIFEST"
