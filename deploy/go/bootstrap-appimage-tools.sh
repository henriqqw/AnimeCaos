#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tools="$root/build/tools"
mkdir -p "$tools"

download_and_verify() {
  local url="$1" destination="$2" expected="$3"
  local temporary="$destination.part"
  curl --fail --location --silent --show-error "$url" -o "$temporary"
  printf '%s  %s\n' "$expected" "$temporary" | sha256sum --check --status || {
    rm -f "$temporary"
    echo "Checksum inválido para a ferramenta de AppImage: $(basename "$destination")" >&2
    exit 1
  }
  mv "$temporary" "$destination"
  chmod +x "$destination"
}

download_and_verify \
  "https://github.com/linuxdeploy/linuxdeploy/releases/download/1-alpha-20251107-1/linuxdeploy-x86_64.AppImage" \
  "$tools/linuxdeploy-x86_64.AppImage" \
  "c20cd71e3a4e3b80c3483cef793cda3f4e990aca14014d23c544ca3ce1270b4d"
download_and_verify \
  "https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/7a3fbc31a9e5075073ff8790f26effbac5f84453/linuxdeploy-plugin-gtk.sh" \
  "$tools/linuxdeploy-plugin-gtk.sh" \
  "b0f4cbc684a0103a9651f0955b635eaea0096b3a66c0f5a2c2aa337960375171"
