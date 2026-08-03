from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class DownloadWorkerSignals(QObject):
    progress = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)
    finished = Signal()


class DownloadWorker(QRunnable):
    def __init__(self, url: str, output_template: str) -> None:
        super().__init__()
        self._url = url
        self._output_template = output_template
        self.signals = DownloadWorkerSignals()
        self._is_cancelled = False
        self._process = None

    def cancel(self):
        self._is_cancelled = True
        if self._process:
            self._process.terminate()

    @Slot()
    def run(self) -> None:
        import subprocess
        from animecaos.core.paths import get_bin_path
        try:
            flags = 0
            if __import__("os").name == "nt":
                flags = subprocess.CREATE_NO_WINDOW
                
            from urllib.parse import urlparse
            parsed = urlparse(self._url)
            referer = f"{parsed.scheme}://{parsed.netloc}/"

            self._process = subprocess.Popen(
                [
                    get_bin_path("yt-dlp"),
                    "-o", self._output_template,
                    "--referer", referer,
                    "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    self._url,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=flags
            )
            for line in iter(self._process.stdout.readline, ""):
                if self._is_cancelled:
                    break
                if line:
                    self.signals.progress.emit(line.strip())
            self._process.stdout.close()
            return_code = self._process.wait()
            
            if self._is_cancelled:
                 self.signals.failed.emit("Download cancelado.")
            elif return_code == 0:
                self.signals.succeeded.emit(self._output_template)
            else:
                self.signals.failed.emit(f"yt-dlp encerrou com erro {return_code}.")
        except FileNotFoundError:
            self.signals.failed.emit("yt-dlp nao encontrado. Instale-o ou adicione ao PATH.")
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        finally:
            self.signals.finished.emit()
