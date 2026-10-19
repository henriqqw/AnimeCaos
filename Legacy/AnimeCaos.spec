# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('public/icon.png', 'public'), ('public/icon.ico', 'public'), ('bin', 'bin')],
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
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['public\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AnimeCaos',
)
