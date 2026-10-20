#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
destination="${1:-$root/bin}"
destination="$(realpath -m "$destination")"
bin_root="$(realpath -m "$root/bin")"
[[ "$destination" == "$bin_root" || "$destination" == "$bin_root/"* ]] || {
  echo 'O destino do runtime do navegador precisa permanecer dentro de bin/.' >&2
  exit 1
}
command -v curl >/dev/null
command -v jq >/dev/null || { echo 'jq é necessário para validar o digest oficial do GeckoDriver.' >&2; exit 1; }
command -v xz >/dev/null

firefox_version=157.0.1
gecko_version=0.37.1
firefox_sha512=ebec5e5c91a7c954a0f276928748bb4249e2b44bccdcfe6c7d7b4ed9c64ca6891a56cc8a016546bfbf1ca537dfe6084dba8f2746037c62fae0acc13a542421f3
gecko_sha256=e815130ea95983e162ae91843b48d3a3ce991735635fce83a647afde21e09f7e
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$destination"

official_gecko_sha256="$(curl --fail --location --silent --show-error \
  -H 'User-Agent: AnimeCaos-release-verifier' \
  "https://api.github.com/repos/mozilla/geckodriver/releases/tags/v$gecko_version" \
  | jq -r '.assets[] | select(.name == "geckodriver-v0.37.1-linux64.tar.gz") | .digest')"
[[ "$official_gecko_sha256" == "sha256:$gecko_sha256" ]] || {
  echo 'Digest fixado diverge da API oficial da release GeckoDriver.' >&2
  exit 1
}

firefox_archive="$work/firefox-$firefox_version.tar.xz"
curl --fail --location --retry 3 --output "$work/firefox-SHA512SUMS" \
  "https://archive.mozilla.org/pub/firefox/releases/$firefox_version/SHA512SUMS"
official_firefox_sha512="$(awk '$2 == "linux-x86_64/en-US/firefox-157.0.1.tar.xz" { print $1 }' "$work/firefox-SHA512SUMS")"
[[ "$official_firefox_sha512" == "$firefox_sha512" ]] || {
  echo 'SHA-512 fixado diverge do manifesto oficial da Mozilla.' >&2
  exit 1
}
curl --fail --location --retry 3 --output "$firefox_archive" \
  "https://archive.mozilla.org/pub/firefox/releases/$firefox_version/linux-x86_64/en-US/firefox-$firefox_version.tar.xz"
echo "$firefox_sha512  $firefox_archive" | sha512sum --check --status || {
  echo 'SHA-512 do Firefox divergiu do manifesto oficial da Mozilla.' >&2
  exit 1
}
rm -rf "$destination/firefox"
mkdir -p "$destination/firefox"
tar -xJf "$firefox_archive" --strip-components=1 -C "$destination/firefox"

gecko_archive="$work/geckodriver-v$gecko_version-linux64.tar.gz"
curl --fail --location --retry 3 --output "$gecko_archive" \
  "https://github.com/mozilla/geckodriver/releases/download/v$gecko_version/geckodriver-v$gecko_version-linux64.tar.gz"
echo "$gecko_sha256  $gecko_archive" | sha256sum --check --status || {
  echo 'SHA-256 do GeckoDriver divergiu do digest oficial da release GitHub.' >&2
  exit 1
}
tar -xzf "$gecko_archive" -C "$work"
install -m 0755 "$work/geckodriver" "$destination/geckodriver"

firefox_report="$("$destination/firefox/firefox" --version)"
gecko_report="$("$destination/geckodriver" --version | head -n 1)"
[[ "$firefox_report" == *"$firefox_version"* ]] || { echo "Firefox inesperado: $firefox_report" >&2; exit 1; }
[[ "$gecko_report" == *"$gecko_version"* ]] || { echo "GeckoDriver inesperado: $gecko_report" >&2; exit 1; }
printf '%s\n%s\n' "$firefox_report" "$gecko_report"
