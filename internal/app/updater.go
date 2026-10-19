package app

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"github.com/henriqqw/animecaos/internal/update"
	"io"
	"os"
	"path/filepath"
	"runtime"
)

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
