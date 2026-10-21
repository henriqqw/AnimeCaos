package app

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"github.com/henriqqw/animecaos/internal/update"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"time"
)

const startupAutoUpdateOperationID = "startup-auto-update"

func startupUpdateTarget(goos, executable, appImage, flatpakID string) (string, bool) {
	switch goos {
	case "windows":
		target := filepath.Dir(executable)
		if _, err := os.Stat(filepath.Join(target, "release-manifest.json")); err != nil {
			return "", false
		}
		return target, true
	case "linux":
		if appImage == "" || flatpakID != "" {
			return "", false
		}
		return appImage, true
	default:
		return "", false
	}
}

func (s *Service) supportsStartupAutoUpdate() bool {
	executable, err := os.Executable()
	if err != nil {
		return false
	}
	_, supported := startupUpdateTarget(runtime.GOOS, executable, os.Getenv("APPIMAGE"), os.Getenv("FLATPAK_ID"))
	return supported
}

// StartStartupAutoUpdate checks for a published release in the background.
// Packaged Windows and AppImage builds download and verify an update while the
// startup splash is visible. Development builds and externally managed Linux
// packages continue starting without checking or replacing files.
func (s *Service) StartStartupAutoUpdate() {
	s.startupUpdateOnce.Do(func() {
		if !s.supportsStartupAutoUpdate() {
			return
		}
		s.setStartupUpdateStatus(StartupUpdateStatus{State: "checking", Done: false})
		go s.runStartupAutoUpdate()
	})
}

func (s *Service) runStartupAutoUpdate() {
	checkCtx, cancelCheck := context.WithTimeout(s.ctx, 8*time.Second)
	info, err := s.updater.Check(checkCtx)
	cancelCheck()
	if err != nil {
		s.setStartupUpdateStatus(StartupUpdateStatus{State: "failed", Done: true})
		return
	}
	if !info.Available || info.Managed {
		s.setStartupUpdateStatus(StartupUpdateStatus{State: "ready", Percent: 100, Done: true})
		return
	}

	s.setStartupUpdateStatus(StartupUpdateStatus{State: "downloading", Version: info.Version, Done: false})
	path, err := s.DownloadUpdate(startupAutoUpdateOperationID, info)
	if err != nil {
		s.setStartupUpdateStatus(StartupUpdateStatus{State: "failed", Version: info.Version, Done: true})
		return
	}
	s.setStartupUpdateStatus(StartupUpdateStatus{State: "installing", Percent: 100, Version: info.Version, Done: false})
	if err := s.InstallUpdate(path); err != nil {
		s.setStartupUpdateStatus(StartupUpdateStatus{State: "failed", Percent: 100, Version: info.Version, Done: true})
	}
}

func (s *Service) StartupUpdateStatus() StartupUpdateStatus {
	s.startupUpdateMu.RLock()
	defer s.startupUpdateMu.RUnlock()
	return s.startupUpdate
}

func (s *Service) setStartupUpdateStatus(status StartupUpdateStatus) {
	s.startupUpdateMu.Lock()
	s.startupUpdate = status
	s.startupUpdateMu.Unlock()
	s.emit("startup-update", status)
}

func digestFile(path string) (string, error) {
	f, e := os.Open(path)
	if e != nil {
		return "", e
	}
	defer f.Close()
	h := sha256.New()
	if _, e = io.Copy(h, f); e != nil {
		return "", e
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
func (s *Service) InstallUpdate(path string) error {
	var expected string
	if s.db.Get("verified_updates", path, &expected) != nil {
		return fmt.Errorf("baixe e verifique o pacote antes de instalar")
	}
	actual, e := digestFile(path)
	if e != nil || actual != expected {
		return fmt.Errorf("pacote modificado após verificação")
	}
	exe, e := os.Executable()
	if e != nil {
		return e
	}
	target := os.Getenv("APPIMAGE")
	if runtime.GOOS == "windows" {
		target = filepath.Dir(exe)
		if _, e = os.Stat(filepath.Join(target, "release-manifest.json")); e != nil {
			return fmt.Errorf("esta é uma compilação de desenvolvimento; instale um pacote de distribuição primeiro")
		}
	} else if target == "" {
		return fmt.Errorf("atualização automática disponível em AppImage; use o gerenciador para Flatpak")
	}
	dir := filepath.Join(s.db.Dir, "updates")
	if e = os.MkdirAll(dir, 0700); e != nil {
		return e
	}
	suffix := ""
	if runtime.GOOS == "windows" {
		suffix = ".exe"
	}
	helper, e := os.CreateTemp(dir, "animecaos-updater-*"+suffix)
	if e != nil {
		return e
	}
	source, e := os.Open(exe)
	if e != nil {
		helper.Close()
		return e
	}
	_, e = io.Copy(helper, source)
	source.Close()
	ce := helper.Close()
	if e != nil {
		return e
	}
	if ce != nil {
		return ce
	}
	if e = os.Chmod(helper.Name(), 0700); e != nil {
		return e
	}
	if e = update.Apply(helper.Name(), path, target, os.Getpid()); e != nil {
		return e
	}
	s.emit("quit", nil)
	return nil
}
