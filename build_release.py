import os
import sys
import shutil
import urllib.request
import zipfile
import tarfile
import subprocess
from pathlib import Path

# Configs
MPV_URL = "https://sourceforge.net/projects/mpv-player-windows/files/64bit/mpv-x86_64-20231231-git-aa8f108.7z/download"
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
GECKODRIVER_URL = "https://github.com/mozilla/geckodriver/releases/download/v0.36.0/geckodriver-v0.36.0-win64.zip"

BASE_DIR = Path(os.path.abspath("."))
BIN_DIR = BASE_DIR / "bin"
TEMP_DIR = BASE_DIR / "temp_build"

def ensure_dirs():
    BIN_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)

def download_file(url, dest_path):
    if not dest_path.exists():
        print(f"Downloading {url} to {dest_path.name}...")
        urllib.request.urlretrieve(url, dest_path)
    else:
        print(f"File {dest_path.name} already exists. Skipping.")

def download_and_extract_zip(url, dest_folder, target_file):
    target_path = dest_folder / target_file
    if target_path.exists():
        print(f"File {target_file} already exists in {dest_folder.name}. Skipping.")
        return
        
    zip_path = TEMP_DIR / "temp.zip"
    download_file(url, zip_path)
    
    print(f"Extracting {target_file} from zip...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file in zip_ref.namelist():
            if file.endswith(target_file):
                zip_ref.extract(file, dest_folder)
                # move if it was in a subfolder
                extracted = dest_folder / file
                if extracted != target_path:
                    shutil.move(str(extracted), str(target_path))
                break

def setup_binaries():
    print("--- Verifying/Downloading Binaries ---")
    ensure_dirs()
    
    # yt-dlp
    download_file(YTDLP_URL, BIN_DIR / "yt-dlp.exe")
    
    # geckodriver
    download_and_extract_zip(GECKODRIVER_URL, BIN_DIR, "geckodriver.exe")
    
    # mpv (since it's a 7z, we assume the user has a local mpv or we just warn if it's missing for simplicity in this script)
    mpv_path = BIN_DIR / "mpv.exe"
    if not mpv_path.exists():
        print("WARNING: mpv.exe not found in bin/. Please download a Windows build of mpv and place mpv.exe in the 'bin' folder before proceeding, as 7z extraction is complex in raw python.")
        print(f"Get it here: {MPV_URL}")

def run_pyinstaller():
    print("--- Running PyInstaller ---")
    # Clean previous builds
    if (BASE_DIR / "build").exists():
        shutil.rmtree(BASE_DIR / "build")
    if (BASE_DIR / "dist").exists():
        shutil.rmtree(BASE_DIR / "dist")
        
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed", # Don't open a console window
        "--icon=public/icon.ico",
        "--name=Animecaos",
        "--add-data=public/icon.png;public",
        "--add-data=public/icon.ico;public",
        "--add-data=bin;bin", # the crucial part: embedding our downloaded binaries!
        "--hidden-import=animecaos.plugins.betteranime",
        "--hidden-import=animecaos.plugins.animesonlinecc",
        "--hidden-import=animecaos.plugins.animefire",
        "main.py"
    ]
    
    subprocess.run(cmd, check=True)
    print("--- Build COMPLETE! Check the 'dist/Animecaos' folder. ---")

if __name__ == "__main__":
    setup_binaries()
    mpv_check = BIN_DIR / "mpv.exe"
    if not mpv_check.exists():
        print("\nERROR: Please put mpv.exe inside the /bin directory before running this script again to finalize the build.")
        sys.exit(1)
        
    run_pyinstaller()
