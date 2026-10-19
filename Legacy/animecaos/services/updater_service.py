import logging
import os
import sys
import json
import urllib.request
import urllib.error
import zipfile
import shutil
import subprocess
from pathlib import Path
from animecaos import __version__

log = logging.getLogger(__name__)


def _select_asset(assets: list[dict], platform: str) -> dict | None:
    """Picks the right GitHub Release asset for the current platform.

    A Release can carry both Windows artifacts (.zip, .exe) and a Linux
    .AppImage side by side — without this, check_for_updates() picked
    ".zip, else .exe" unconditionally, so a Linux user would silently be
    offered the Windows .zip.
    """
    if platform.startswith("linux"):
        return next((a for a in assets if a.get("name", "").endswith(".AppImage")), None)
    zip_asset = next((a for a in assets if a.get("name", "").endswith(".zip")), None)
    exe_asset = next((a for a in assets if a.get("name", "").endswith(".exe")), None)
    return zip_asset or exe_asset


class UpdaterService:
    """Servico para checar atualizacoes usando a API do GitHub Releases."""
    
    API_URL = "https://api.github.com/repos/henriqqw/animecaos/releases/latest"
    
    def __init__(self):
        self.current_version = __version__
        self.latest_version = __version__
        self.download_url = None
        self.download_name = ""
        self.release_notes = ""

    def check_for_updates(self) -> bool:
        """Verifica se existe uma versao mais recente no GitHub."""
        try:
            req = urllib.request.Request(self.API_URL)
            req.add_header("User-Agent", "Animecaos-Updater")
            req.add_header("Accept", "application/vnd.github.v3+json")
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                tag_name = data.get("tag_name", "") # ex: "v0.1.1"
                if tag_name.startswith("v"):
                    tag_name = tag_name[1:]
                    
                self.latest_version = tag_name
                self.release_notes = data.get("body", "")
                
                assets = data.get("assets", [])
                target_asset = _select_asset(assets, sys.platform)

                if target_asset:
                    self.download_url = target_asset.get("browser_download_url")
                    self.download_name = target_asset.get("name", "")
                
                return self._is_newer_version(self.latest_version, self.current_version)
        except Exception as e:
            log.warning("Erro ao checar atualizacoes: %s", e)
            return False

    def _is_newer_version(self, latest: str, current: str) -> bool:
        """Compara duas strings de versao semantica."""
        try:
            l_parts = [int(p) for p in latest.split(".")]
            c_parts = [int(p) for p in current.split(".")]
            for l, c in zip(l_parts, c_parts):
                if l > c: return True
                if l < c: return False
            return len(l_parts) > len(c_parts)
        except Exception:
            return False

    def perform_update(self, callback_progress=None) -> bool:
        """Processo de download e substituicao do binario."""
        if not self.download_url:
            return False

        if sys.platform.startswith("linux"):
            return self._perform_update_linux(callback_progress)

        try:
            is_frozen = getattr(sys, 'frozen', False)
            if is_frozen:
                base_dir = Path(sys.executable).parent
                exe_name = Path(sys.executable).name
            else:
                base_dir = Path(os.path.abspath("."))
                exe_name = "main.py"
                
            temp_dir = base_dir / "update_temp"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True)
            
            download_path = temp_dir / self.download_name
            
            # 1. Download
            def hook(count, block_size, total_size):
                if callback_progress:
                    percent = int(count * block_size * 100 / total_size) if total_size > 0 else 0
                    callback_progress(min(percent, 100))
            
            urllib.request.urlretrieve(self.download_url, download_path, reporthook=hook if callback_progress else None)

            # Ensure file is fully written
            if download_path.exists():
                with open(download_path, 'ab') as f:
                    os.fsync(f.fileno())

            # 2. Preparation (Extract or Move)
            new_app_dir = temp_dir
            if self.download_name.endswith(".zip"):
                if callback_progress: callback_progress("Extracao")
                extract_dir = temp_dir / "extracted"
                with zipfile.ZipFile(download_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                new_app_dir = extract_dir
                for item in extract_dir.iterdir():
                    if item.is_dir() and (item / "Animecaos.exe").exists():
                        new_app_dir = item
                        break
            else:
                # Direct .exe update: we have the standalone file in temp_dir / download_name
                # We will handle the move in the batch script
                pass

            # 3. Batch script for hot-swap
            bat_path = base_dir / "update.bat"
            log_path = base_dir / "updater.log"
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write("@echo off\n")
                f.write(f'echo [%DATE% %TIME%] Update started by {exe_name} >> "{log_path}"\n')
                f.write('echo Aplicando atualizacao...\n')
                f.write('timeout /t 3 /nobreak > NUL\n')

                # Safeguard: ensure process is truly dead
                if is_frozen:
                    f.write(f'taskkill /F /IM "{exe_name}" /T >> "{log_path}" 2>&1\n')
                    f.write('timeout /t 3 /nobreak > NUL\n')
                    # Clean stale PyInstaller _MEI temp dirs to avoid DLL conflicts
                    f.write(f'echo [%DATE% %TIME%] Cleaning old _MEI dirs >> "{log_path}"\n')
                    f.write('for /d %%D in ("%TEMP%\\_MEI*") do rmdir /s /q "%%D" >> "{}" 2>&1\n'.format(log_path))
                    f.write('timeout /t 2 /nobreak > NUL\n')

                if self.download_name.endswith(".zip"):
                    f.write(f'echo [%DATE% %TIME%] Copying from zip extracted dir >> "{log_path}"\n')
                    f.write(f'xcopy "{new_app_dir}\\*" "{base_dir}" /E /Y /C /R /Q >> "{log_path}" 2>&1\n')
                elif is_frozen:
                    # Only move/overwrite if we are actually running from an EXE
                    target_exe = base_dir / exe_name
                    f.write(f'echo [%DATE% %TIME%] Moving standalone exe to {exe_name} >> "{log_path}"\n')
                    f.write(f'move /Y "{download_path}" "{target_exe}" >> "{log_path}" 2>&1\n')
                else:
                    # Dev mode: just keep the downloaded exe for inspection, don't overwrite main.py!
                    f.write(f'echo [%DATE% %TIME%] Dev mode: keeping {self.download_name} without overwriting scripts >> "{log_path}"\n')

                f.write(f'rmdir /s /q "{temp_dir}" >> "{log_path}" 2>&1\n')
                f.write(f'echo [%DATE% %TIME%] Attempting restart >> "{log_path}"\n')

                if is_frozen:
                    f.write(f'start "" "{base_dir}\\{exe_name}"\n')
                else:
                    f.write(f'start "" python "{base_dir}\\main.py"\n')

                f.write(f'echo [%DATE% %TIME%] Batch script finished >> "{log_path}"\n')
                f.write('del "%~f0"\n')

            subprocess.Popen([str(bat_path)], shell=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            return True
            
        except Exception as e:
            log.error("Erro efetuando update: %s", e)
            if callback_progress: callback_progress(-1)
            return False

    def _perform_update_linux(self, callback_progress=None) -> bool:
        """AppImage self-update: downloads the new .AppImage into the SAME
        directory as the running one (so the final os.replace() is atomic —
        that only holds within a single filesystem, and /tmp is often a
        different one from wherever the AppImage actually lives), swaps it
        in, and re-execs into it.

        Only works when actually running from an AppImage — the AppImage
        runtime sets $APPIMAGE to the mounted file's own path; running from
        source on Linux has nothing to self-update, so this just declines.
        """
        appimage_path = os.environ.get("APPIMAGE")
        if not appimage_path:
            log.warning("Auto-update indisponivel: app nao esta rodando a partir de um AppImage.")
            return False

        target = Path(appimage_path)
        download_path = target.parent / f"{target.name}.new"
        try:
            def hook(count, block_size, total_size):
                if callback_progress:
                    percent = int(count * block_size * 100 / total_size) if total_size > 0 else 0
                    callback_progress(min(percent, 100))

            urllib.request.urlretrieve(self.download_url, download_path, reporthook=hook if callback_progress else None)

            if download_path.exists():
                with open(download_path, "ab") as f:
                    os.fsync(f.fileno())

            os.chmod(download_path, 0o755)
            os.replace(download_path, target)

            os.execv(str(target), [str(target)])
            return True
        except Exception as e:
            log.error("Erro efetuando update (Linux): %s", e)
            if callback_progress: callback_progress(-1)
            try:
                download_path.unlink(missing_ok=True)
            except OSError:
                pass
            return False
