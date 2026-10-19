#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
stage="$(realpath "${1:?Informe o stage Linux gerado por go run ./cmd/package}")"
version="${2:-3.0.0-dev}"
tool="${LINUXDEPLOY:-$root/build/tools/linuxdeploy-x86_64.AppImage}"
[[ "$stage" == "$root/release/stage-linux-"* && -f "$stage/AnimeCaos" ]] || { echo 'Stage Linux inválido' >&2; exit 1; }
[[ "$version" =~ ^[0-9A-Za-z._-]+$ ]] || { echo 'Versão inválida' >&2; exit 1; }
[[ -x "$tool" ]] || { echo 'Instale linuxdeploy e linuxdeploy-plugin-gtk em build/tools' >&2; exit 1; }
pkg-config --exists gtk+-3.0 webkit2gtk-4.1 librsvg-2.0 gobject-introspection-1.0
appdir="$(mktemp -d "$root/release/AnimeCaos.AppDir.XXXXXX")"
mkdir -p "$appdir/usr/bin" "$appdir/usr/lib/webkit2gtk-4.1" "$appdir/usr/lib/x86_64-linux-gnu" "$appdir/apprun-hooks"
cp "$stage/AnimeCaos" "$stage/animecaos-cli" "$stage/release-manifest.json" "$appdir/usr/bin/"
cp "$stage/bin/mpv" "$stage/bin/ffmpeg" "$stage/bin/ffprobe" "$appdir/usr/bin/"
"$stage/bin/ffmpeg" -v error -y -i "$root/public/icon.png" -vf scale=512:512 -frames:v 1 "$appdir/com.animecaos.App.png"
libdir="$(pkg-config --variable=libdir webkit2gtk-4.1)"
webkit="$libdir/webkit2gtk-4.1"
cp -a "$webkit/". "$appdir/usr/lib/webkit2gtk-4.1/"
# WebKitGTK release builds use a fixed Debian helper path. AppRun starts from usr/,
# so make that path available inside the bundle for its subprocesses.
ln -sfn ../../lib/webkit2gtk-4.1 "$appdir/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1"
if [[ -d "$libdir/gio/modules" ]]; then
  mkdir -p "$appdir/usr/lib/gio/modules"
  cp -a "$libdir/gio/modules/". "$appdir/usr/lib/gio/modules/"
fi
cat > "$appdir/apprun-hooks/animecaos.sh" <<'HOOK'
export PATH="$APPDIR/usr/bin:$PATH"
# WEBKIT_EXEC_PATH is ignored by release WebKitGTK; helper path is patched in libwebkit2gtk.
export LD_LIBRARY_PATH="$APPDIR/usr/lib:$APPDIR/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export WEBKIT_INJECTED_BUNDLE_PATH="$APPDIR/usr/lib/webkit2gtk-4.1/injected-bundle"
export GIO_EXTRA_MODULES="$APPDIR/usr/lib/gio/modules"
HOOK
args=(--appdir "$appdir" --executable "$appdir/usr/bin/AnimeCaos" --executable "$appdir/usr/bin/animecaos-cli")
for binary in mpv ffmpeg ffprobe; do args+=(--executable "$appdir/usr/bin/$binary"); done
# Patch the compiled /usr prefix to a same-length relative path. AppRun changes cwd to usr/.
while IFS= read -r -d '' library; do
  if grep -aq "/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1" "$library"; then
    sed -i -e "s#/usr#././#g" "$library"
  fi
done < <(find "$appdir/usr/lib" -type f -name "libwebkit2gtk*.so*" -print0)
for binary in WebKitNetworkProcess WebKitWebProcess WebKitGPUProcess; do
  if [[ -x "$webkit/$binary" ]]; then args+=(--deploy-deps-only "$appdir/usr/lib/webkit2gtk-4.1/$binary"); fi
done
while IFS= read -r -d '' library; do args+=(--library "$library"); done < <(find "$appdir/usr/lib/webkit2gtk-4.1/injected-bundle" "$appdir/usr/lib/gio/modules" -type f -name '*.so' -print0)
export APPIMAGE_EXTRACT_AND_RUN=1 DEPLOY_GTK_VERSION=3
export PATH="$(dirname "$tool"):$PATH"
export OUTPUT="$root/release/AnimeCaos-$version-x86_64.AppImage"
[[ ! -e "$OUTPUT" ]] || { echo 'O arquivo de saída já existe' >&2; exit 1; }
"$tool" "${args[@]}" --plugin gtk --desktop-file "$root/deploy/go/com.animecaos.App.desktop" --icon-file "$appdir/com.animecaos.App.png" --output appimage
cd "$root/release"
sha256sum "$(basename "$OUTPUT")" >> SHA256SUMS
printf 'AppImage: %s\nAppDir: %s\n' "$OUTPUT" "$appdir"
