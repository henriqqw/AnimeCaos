#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
stage="$(realpath "${1:?Informe o stage Linux gerado por go run ./cmd/package}")"
version="${2:-3.0.2}"
tool="${LINUXDEPLOY:-$root/build/tools/linuxdeploy-x86_64.AppImage}"
[[ "$stage" == "$root/release/stage-linux-"* && -f "$stage/AnimeCaos" ]] || { echo 'Stage Linux inválido' >&2; exit 1; }
[[ "$version" =~ ^[0-9A-Za-z._-]+$ ]] || { echo 'Versão inválida' >&2; exit 1; }
[[ -x "$tool" ]] || { echo 'Instale linuxdeploy e linuxdeploy-plugin-gtk em build/tools' >&2; exit 1; }
pkg-config --exists gtk+-3.0 webkit2gtk-4.1 librsvg-2.0 gobject-introspection-1.0
appdir="$(mktemp -d "$root/release/AnimeCaos.AppDir.XXXXXX")"
mkdir -p "$appdir/usr/bin" "$appdir/usr/lib/firefox" "$appdir/usr/lib/webkit2gtk-4.1" "$appdir/usr/lib/x86_64-linux-gnu" "$appdir/apprun-hooks"
cp "$stage/AnimeCaos" "$stage/animecaos-cli" "$stage/release-manifest.json" "$appdir/usr/bin/"
mkdir -p "$appdir/usr/share/licenses/AnimeCaos/licenses"
cp "$stage/DISTRIBUTION.md" "$stage/THIRD-PARTY-NOTICES.md" "$appdir/usr/share/licenses/AnimeCaos/"
cp -a "$stage/licenses/". "$appdir/usr/share/licenses/AnimeCaos/licenses/"
cp "$stage/bin/mpv" "$stage/bin/ffmpeg" "$stage/bin/ffprobe" "$appdir/usr/bin/"
cp "$stage/bin/geckodriver" "$appdir/usr/bin/"
cp -a "$stage/bin/firefox/". "$appdir/usr/lib/firefox/"
browser_backup="$root/release/browser-runtime.$$.tmp"
mkdir -p "$browser_backup"
cp "$appdir/usr/bin/geckodriver" "$browser_backup/geckodriver"
cp -a "$appdir/usr/lib/firefox" "$browser_backup/firefox"
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
export LD_LIBRARY_PATH="$APPDIR/usr/lib/firefox:$APPDIR/usr/lib:$APPDIR/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export WEBKIT_INJECTED_BUNDLE_PATH="$APPDIR/usr/lib/webkit2gtk-4.1/injected-bundle"
export GIO_EXTRA_MODULES="$APPDIR/usr/lib/gio/modules"
HOOK
args=(--appdir "$appdir" --executable "$appdir/usr/bin/AnimeCaos")
for binary in mpv ffmpeg ffprobe; do args+=(--executable "$appdir/usr/bin/$binary"); done
# Keep Firefox and GeckoDriver as untouched upstream files. linuxdeploy patches
# RPATH even with --deploy-deps-only, which breaks GeckoDriver's static PIE and
# Firefox's own launcher. Firefox ships its private libraries and AppRun adds
# that directory to LD_LIBRARY_PATH.
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
ldd_wrapper_dir="$(mktemp -d "$root/release/ldd-wrapper.XXXXXX")"
cli_hold=""
cleanup_build_helpers() {
  if [[ -n "$cli_hold" && -e "$cli_hold" ]]; then
    mv "$cli_hold" "$appdir/usr/bin/animecaos-cli"
  fi
  cleanup_paths=("$ldd_wrapper_dir" "$browser_backup")
  if [[ -n "${appimagetool_dir:-}" ]]; then cleanup_paths+=("$appimagetool_dir"); fi
  rm -rf "${cleanup_paths[@]}"
}
trap cleanup_build_helpers EXIT
cat > "$ldd_wrapper_dir/ldd" <<'LDD_WRAPPER'
#!/usr/bin/env bash
LD_LIBRARY_PATH="${ANIMECAOS_LINUXDEPLOY_FIREFOX_LIBDIR}:${LD_LIBRARY_PATH:-}" exec /usr/bin/ldd "$@"
LDD_WRAPPER
chmod 0755 "$ldd_wrapper_dir/ldd"
export ANIMECAOS_LINUXDEPLOY_FIREFOX_LIBDIR="$appdir/usr/lib/firefox"
export PATH="$ldd_wrapper_dir:$(dirname "$tool"):$PATH"
export OUTPUT="$root/release/AnimeCaos-$version-x86_64.AppImage"
if [[ -e "$OUTPUT" ]]; then rm -f -- "$OUTPUT"; fi
# The input pass first fills AppDir. Collect Debian copyright notices for the
# runtime libraries linuxdeploy selected before the output plugin creates the
# AppImage; this keeps the notices tied to the actual dependency graph.
cli_hold="$root/release/animecaos-cli.$$.tmp"
mv "$appdir/usr/bin/animecaos-cli" "$cli_hold"
"$tool" "${args[@]}" --plugin gtk --desktop-file "$root/deploy/go/com.animecaos.App.desktop" --icon-file "$appdir/com.animecaos.App.png"
mv "$cli_hold" "$appdir/usr/bin/animecaos-cli"
cli_hold=""
system_licenses="$appdir/usr/share/licenses/AnimeCaos/licenses/system"
mkdir -p "$system_licenses"
declare -A runtime_packages=()
declare -A system_library_paths=()
declare -A source_package_cache=()
ldconfig_command="$(command -v ldconfig || true)"
if [[ -z "$ldconfig_command" && -x /sbin/ldconfig ]]; then ldconfig_command=/sbin/ldconfig; fi
if [[ -n "$ldconfig_command" ]]; then
  while IFS=' ' read -r library_name library_path; do
    [[ -n "$library_name" && -n "$library_path" ]] || continue
    [[ -n "${system_library_paths[$library_name]:-}" ]] || system_library_paths["$library_name"]="$library_path"
  done < <("$ldconfig_command" -p | awk '$3 == "=>" { print $1, $4 }')
fi
while IFS= read -r -d '' binary; do
  if ! readelf -h "$binary" >/dev/null 2>&1; then continue; fi
  while IFS= read -r dependency; do
    [[ -f "$dependency" ]] || continue
    source_dependency="$dependency"
    if [[ "$dependency" == "$appdir"/* ]]; then
      dependency_name="$(basename "$dependency")"
      if [[ -n "${system_library_paths[$dependency_name]+cached}" ]]; then
        source_dependency="${system_library_paths[$dependency_name]}"
      else
        source_dependency="$(find /usr/lib /lib \( -type f -o -type l \) -name "$dependency_name" -print -quit 2>/dev/null || true)"
        system_library_paths["$dependency_name"]="$source_dependency"
      fi
    fi
    [[ -n "$source_dependency" ]] || continue
    if [[ -n "${source_package_cache[$source_dependency]+cached}" ]]; then
      package_owners="${source_package_cache[$source_dependency]}"
    else
      package_owners="$(dpkg-query -S -- "$source_dependency" 2>/dev/null | sed -n 's/: \/.*$//p' || true)"
      if [[ -z "$package_owners" ]]; then
        canonical_dependency="$(realpath "$source_dependency" 2>/dev/null || true)"
        if [[ -n "$canonical_dependency" && "$canonical_dependency" != "$source_dependency" ]]; then
          package_owners="$(dpkg-query -S -- "$canonical_dependency" 2>/dev/null | sed -n 's/: \/.*$//p' || true)"
        fi
      fi
      source_package_cache["$source_dependency"]="$package_owners"
    fi
    while IFS= read -r owner; do
      if [[ -n "$owner" ]]; then runtime_packages["$owner"]=1; fi
    done <<< "$package_owners"
  done < <(ldd "$binary" 2>/dev/null | grep -oE '/[^[:space:]]+' || true)
done < <(find "$appdir/usr" -type f -print0)
printf 'package\tversion\n' > "$system_licenses/packages.tsv"
while IFS= read -r package; do
  [[ -n "$package" ]] || continue
  version_line="$(dpkg-query -W -f='${binary:Package}\t${Version}' "$package" 2>/dev/null || true)"
  [[ -n "$version_line" ]] || continue
  printf '%s\n' "$version_line" >> "$system_licenses/packages.tsv"
  base_package="${package%%:*}"
  copyright_file="/usr/share/doc/$base_package/copyright"
  if [[ -f "$copyright_file" ]]; then
    safe_name="$(printf '%s' "$package" | tr -c 'A-Za-z0-9._+-' '_')"
    mkdir -p "$system_licenses/$safe_name"
    cp -L "$copyright_file" "$system_licenses/$safe_name/copyright"
  fi
done < <(printf '%s\n' "${!runtime_packages[@]}" | sort)
if [[ "$(wc -l < "$system_licenses/packages.tsv")" -le 1 ]]; then
  echo 'Não foi possível mapear as bibliotecas AppImage para pacotes/licenças da distribuição' >&2
  exit 1
fi
# linuxdeploy's appimage output pass scans and patches executables again. Put
# the pristine upstream browser files back first, then package the finished
# AppDir directly with the same appimagetool bundled inside linuxdeploy.
rm -rf "$appdir/usr/lib/firefox"
mv "$browser_backup/firefox" "$appdir/usr/lib/firefox"
rm -f "$appdir/usr/bin/geckodriver"
mv "$browser_backup/geckodriver" "$appdir/usr/bin/geckodriver"
cmp -s "$stage/bin/geckodriver" "$appdir/usr/bin/geckodriver" || { echo 'GeckoDriver foi alterado durante o empacotamento' >&2; exit 1; }
cmp -s "$stage/bin/firefox/firefox" "$appdir/usr/lib/firefox/firefox" || { echo 'O launcher do Firefox foi alterado durante o empacotamento' >&2; exit 1; }
appimagetool_dir="$(mktemp -d "$root/release/linuxdeploy-runtime.XXXXXX")"
(
  cd "$appimagetool_dir"
  APPIMAGE_EXTRACT_AND_RUN=0 "$tool" --appimage-extract >/dev/null
)
appimagetool="$appimagetool_dir/squashfs-root/plugins/linuxdeploy-plugin-appimage/usr/bin/appimagetool"
[[ -x "$appimagetool" ]] || { echo 'Não foi possível localizar o appimagetool incluído no linuxdeploy' >&2; exit 1; }
"$appimagetool" --no-appstream "$appdir" "$OUTPUT"
cd "$root/release"
checksum_tmp="$(mktemp "$root/release/SHA256SUMS.XXXXXX")"
if [[ -f "$root/release/SHA256SUMS" ]]; then
  awk -v name="$(basename "$OUTPUT")" '$2 != name { print }' "$root/release/SHA256SUMS" > "$checksum_tmp"
fi
sha256sum "$(basename "$OUTPUT")" >> "$checksum_tmp"
mv -f -- "$checksum_tmp" "$root/release/SHA256SUMS"
printf 'AppImage: %s\nAppDir: %s\n' "$OUTPUT" "$appdir"
