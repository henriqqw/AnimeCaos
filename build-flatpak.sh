#!/usr/bin/env bash
# Build and install the Animecaos Flatpak locally.
# Run on Linux with flatpak and flatpak-builder installed.
#
# Usage:
#   ./build-flatpak.sh            # build + install for current user
#   ./build-flatpak.sh --export   # build + export .flatpak bundle file

set -euo pipefail

APP_ID="com.animecaos.App"
MANIFEST="com.animecaos.App.yaml"
BUILD_DIR=".flatpak-build"
REPO_DIR=".flatpak-repo"

# Verify dependencies
for cmd in flatpak flatpak-builder; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: '$cmd' not found. Install with: sudo apt install flatpak flatpak-builder"
        exit 1
    fi
done

# Add Flathub remote for current user (--user avoids needing sudo)
if ! flatpak remote-list --user | grep -q flathub; then
    echo "Adding Flathub remote..."
    flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
fi

# Install required runtime and SDK if missing
echo "Checking runtimes..."
flatpak install --user -y flathub \
    org.freedesktop.Platform//24.08 \
    org.freedesktop.Sdk//24.08 \
    org.freedesktop.Sdk.Extension.python312//24.08 \
    2>/dev/null || true

# Update checksums for geckodriver if not filled in yet
if grep -q "GECKO_SHA256_" "$MANIFEST" 2>/dev/null; then
    echo "Fetching geckodriver checksums..."
    bash update-checksums.sh
fi

echo "Building Flatpak..."
flatpak-builder \
    --force-clean \
    --user \
    --install \
    --repo="$REPO_DIR" \
    "$BUILD_DIR" \
    "$MANIFEST"

echo ""
echo "Build complete! Run the app with:"
echo "  flatpak run $APP_ID"

if [[ "${1:-}" == "--export" ]]; then
    echo ""
    echo "Exporting .flatpak bundle..."
    flatpak build-bundle \
        "$REPO_DIR" \
        "Animecaos.flatpak" \
        "$APP_ID"
    echo "Bundle saved: Animecaos.flatpak"
    echo "Install on another machine with: flatpak install Animecaos.flatpak"
fi
