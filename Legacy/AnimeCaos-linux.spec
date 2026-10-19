# -*- mode: python ; coding: utf-8 -*-
#
# Linux build. Differs from AnimeCaos.spec (Windows) in two ways:
#   - no icon= on EXE: that's a Windows PE resource, meaningless on Linux —
#     the app icon there comes from the .desktop file + hicolor icon theme
#     instead (see deploy/appimage/).
#   - no bin/ in datas: bin/ only holds Windows binaries (mpv.exe,
#     yt-dlp.exe, geckodriver.exe). The Linux release doesn't bundle mpv
#     (relies on the system's — see DependencyService); yt-dlp is fetched
#     as a Linux binary and placed into the AppDir separately by the
#     release workflow, not baked into this .spec.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('public/icon.png', 'public')],
    hiddenimports=['animecaos.plugins.animefire', 'animecaos.plugins.animesonlinecc', 'animecaos.plugins.betteranime', 'animecaos.plugins.url_cache', 'animecaos.services.config_service', 'animecaos.services.anilist_auth_service', 'animecaos.services.anilist_service', 'animecaos.services.anilist_rate_limiter', 'animecaos.services.discord_service', 'animecaos.services.downloads_service', 'animecaos.services.history_service', 'animecaos.services.updater_service', 'animecaos.services.watchlist_service', 'animecaos.services.anime_service', 'animecaos.services.manga_service', 'animecaos.services.manga_download_service', 'animecaos.services.manga_history_service', 'pypresence'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AnimeCaos',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AnimeCaos',
)
