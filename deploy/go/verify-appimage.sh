#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
appimage="$(realpath "${1:?Informe o AppImage}")"
data_dir="$(realpath -m "${2:?Informe um diretório de dados de teste}")"
root="$(mktemp -d)"
target="$root/AnimeCaos.AppImage"
database="$data_dir/state.db"
mkdir -p "$data_dir"
cp "$appimage" "$target"
chmod +x "$target"

run_app_until_database_exists() {
  local image="$1" log="$root/appimage-startup.log" status=0
  export APPIMAGE_EXTRACT_AND_RUN=1 ANIMECAOS_DATA_DIR="$data_dir" GDK_BACKEND=x11
  set +e
  timeout --signal=TERM --kill-after=5s 18s xvfb-run -a dbus-run-session -- "$image" >"$log" 2>&1
  status=$?
  set -e
  if [[ "$status" -ne 124 && "$status" -ne 137 ]]; then
    cat "$log" >&2
    echo "O AppImage encerrou inesperadamente (exit=$status)" >&2
    return 1
  fi
  if [[ ! -s "$database" ]]; then
    cat "$log" >&2
    echo "AnimeCaos não criou state.db durante a execução do AppImage" >&2
    return 1
  fi
}

run_app_until_database_exists "$target"
before="$(sha256sum "$database" | cut -d' ' -f1)"

# Exercise the exact browser and media executables from the built AppImage,
# with its bundled shared libraries taking precedence over the host system.
mkdir -p "$root/extract"
(
  cd "$root/extract"
  APPIMAGE_EXTRACT_AND_RUN=0 "$target" --appimage-extract >"$root/extract.log" 2>&1
)
appdir="$root/extract/squashfs-root"
for binary in mpv ffmpeg ffprobe geckodriver; do
  [[ -x "$appdir/usr/bin/$binary" ]] || { cat "$root/extract.log" >&2; echo "O AppImage não contém $binary" >&2; exit 1; }
done
[[ -x "$appdir/usr/lib/firefox/firefox" ]] || { echo 'O AppImage não contém Firefox.' >&2; exit 1; }
export APPDIR="$appdir"
export LD_LIBRARY_PATH="$appdir/usr/lib/firefox:$appdir/usr/lib:$appdir/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="$appdir/usr/bin:$PATH"
"$appdir/usr/bin/mpv" --version >/dev/null
"$appdir/usr/bin/ffmpeg" -version >/dev/null
"$appdir/usr/bin/ffprobe" -version >/dev/null
export ANIMECAOS_PLAYER_TEST=1
(
  cd "$repo_root"
  go test ./internal/player -run '^TestMPVIntegration$' -count=1
)
export ANIMECAOS_BROWSER_TEST=1 ANIMECAOS_BROWSER_HEADLESS=1
export ANIMECAOS_FIREFOX_PATH="$appdir/usr/lib/firefox/firefox"
export ANIMECAOS_GECKODRIVER_PATH="$appdir/usr/bin/geckodriver"
(
  cd "$repo_root"
  go test ./internal/providers -run '^TestBundledFirefoxDynamicPlayerFixture$' -count=1
)

export APPIMAGE_EXTRACT_AND_RUN=1 ANIMECAOS_DATA_DIR="$data_dir" GDK_BACKEND=x11
export UPDATE_TARGET="$target" UPDATE_PACKAGE="$appimage"
set +e
timeout --signal=TERM --kill-after=5s 18s xvfb-run -a dbus-run-session -- bash -c '
  "$UPDATE_TARGET" --apply-update "$UPDATE_PACKAGE" --target "$UPDATE_TARGET" --parent 2147483647
  sleep 8
' >"$root/update.log" 2>&1
status=$?
set -e
if [[ "$status" -ne 0 && "$status" -ne 124 && "$status" -ne 137 ]]; then
  cat "$root/update.log" >&2
  echo "O teste do updater encerrou inesperadamente (exit=$status)" >&2
  exit 1
fi
if [[ -s "$root/updater-error.log" ]]; then
  cat "$root/updater-error.log" >&2
  echo "O helper do updater registrou uma falha" >&2
  exit 1
fi
if [[ -e "$target.failed" ]] || ! compgen -G "$target.previous-*" >/dev/null; then
  cat "$root/update.log" >&2
  echo "O updater não substituiu o AppImage nem preservou um backup" >&2
  exit 1
fi
if [[ ! -s "$database" ]]; then
  cat "$root/update.log" >&2
  echo "O AppImage atualizado não criou state.db" >&2
  exit 1
fi
after="$(sha256sum "$database" | cut -d' ' -f1)"
[[ "$before" == "$after" ]] || { echo "O update alterou state.db" >&2; exit 1; }

echo "AppImage abriu, aplicou atualização e preservou state.db."
rm -rf "$root" "${target}.previous-"*
