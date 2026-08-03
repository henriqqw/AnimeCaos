#!/usr/bin/env sh
set -eu

BUILD_CMD="pyinstaller -n animecaos --onefile --icon=icon.ico --add-data \"icon.png;.\" main.py --hidden-import animecaos --hidden-import animecaos.plugins"

for plugin_path in animecaos/plugins/*.py; do
    plugin_module=$(printf "%s" "$plugin_path" | sed 's/\.py$//' | sed 's#/#.#g')
    if [ "$plugin_module" = "animecaos.plugins.__init__" ] || [ "$plugin_module" = "animecaos.plugins.utils" ]; then
        continue
    fi
    BUILD_CMD="$BUILD_CMD --hidden-import $plugin_module"
done

echo "$BUILD_CMD"
eval "$BUILD_CMD"

echo "Build concluido. Binario em dist/animecaos"
