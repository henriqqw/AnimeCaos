import os
import sys
import shutil
import urllib.request
import zipfile
import subprocess
from pathlib import Path

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
GECKODRIVER_URL = "https://github.com/mozilla/geckodriver/releases/download/v0.36.0/geckodriver-v0.36.0-win64.zip"
MPV_URL = "https://sourceforge.net/projects/mpv-player-windows/files/64bit/mpv-x86_64-20231231-git-aa8f108.7z/download"

BASE_DIR = Path(os.path.abspath("."))
BIN_DIR = BASE_DIR / "bin"
TEMP_DIR = BASE_DIR / "temp_build"


def ensure_dirs():
    BIN_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)


def download_file(url, dest_path):
    if not dest_path.exists():
        print(f"  Baixando {dest_path.name}...")
        urllib.request.urlretrieve(url, dest_path)
    else:
        print(f"  {dest_path.name} ja existe, pulando.")


def download_and_extract_zip(url, dest_folder, target_file):
    target_path = dest_folder / target_file
    if target_path.exists():
        print(f"  {target_file} ja existe, pulando.")
        return
    zip_path = TEMP_DIR / "temp.zip"
    download_file(url, zip_path)
    print(f"  Extraindo {target_file}...")
    with zipfile.ZipFile(zip_path, "r") as z:
        for name in z.namelist():
            if name.endswith(target_file):
                z.extract(name, dest_folder)
                extracted = dest_folder / name
                if extracted != target_path:
                    shutil.move(str(extracted), str(target_path))
                break


def setup_binaries():
    print("\n[1/3] Verificando binarios...")
    ensure_dirs()
    download_file(YTDLP_URL, BIN_DIR / "yt-dlp.exe")
    download_and_extract_zip(GECKODRIVER_URL, BIN_DIR, "geckodriver.exe")
    mpv_path = BIN_DIR / "mpv.exe"
    if not mpv_path.exists():
        print(f"\n  AVISO: mpv.exe nao encontrado em bin/")
        print(f"  Baixe em: {MPV_URL}")
        print(f"  Extraia mpv.exe para a pasta bin/ e rode o script novamente.")
        sys.exit(1)
    print("  Binarios OK.")


def run_pyinstaller():
    print("\n[2/3] Rodando PyInstaller...")
    for d in ["build", "dist"]:
        p = BASE_DIR / d
        if p.exists():
            shutil.rmtree(p)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--icon=public/icon.ico",
        "--name=AnimeCaos",
        "--add-data=public/icon.png;public",
        "--add-data=public/icon.ico;public",
        "--add-data=bin;bin",
        # plugins
        "--hidden-import=animecaos.plugins.animefire",
        "--hidden-import=animecaos.plugins.animesonlinecc",
        "--hidden-import=animecaos.plugins.betteranime",
        "--hidden-import=animecaos.plugins.player_cache",
        # services
        "--hidden-import=animecaos.services.config_service",
        "--hidden-import=animecaos.services.anilist_auth_service",
        "--hidden-import=animecaos.services.anilist_service",
        "--hidden-import=animecaos.services.discord_service",
        "--hidden-import=animecaos.services.downloads_service",
        "--hidden-import=animecaos.services.history_service",
        "--hidden-import=animecaos.services.updater_service",
        "--hidden-import=animecaos.services.watchlist_service",
        "--hidden-import=animecaos.services.anime_service",
        # optional deps loaded at runtime
        "--hidden-import=pypresence",
        "main.py",
    ]

    subprocess.run(cmd, check=True)


def run_inno_setup():
    print("\n[3/3] Gerando instalador com Inno Setup...")
    iscc_candidates = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    iscc = next((p for p in iscc_candidates if p.exists()), None)
    if not iscc:
        print("  AVISO: Inno Setup nao encontrado.")
        print("  Instale em https://jrsoftware.org/isinfo.php e rode novamente,")
        print("  ou compile setup.iss manualmente.")
        return
    subprocess.run([str(iscc), "setup.iss"], check=True)
    installer_dir = BASE_DIR / "installer"
    installers = list(installer_dir.glob("Setup_AnimeCaos_*.exe"))
    if installers:
        print(f"\n  Instalador gerado: {installers[-1].name}")


if __name__ == "__main__":
    print("=== AnimeCaos — Windows Release Build ===")
    setup_binaries()
    run_pyinstaller()
    run_inno_setup()
    print("\n=== Build concluido! ===")
    print("  EXE:       dist/AnimeCaos/AnimeCaos.exe")
    print("  Instalador: installer/Setup_AnimeCaos_*.exe")
