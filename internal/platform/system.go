package platform

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

func DataDir() string {
	if p := os.Getenv("ANIMECAOS_DATA_DIR"); p != "" {
		return p
	}
	h, _ := os.UserHomeDir()
	if runtime.GOOS == "windows" {
		p := os.Getenv("APPDATA")
		if p == "" {
			p = filepath.Join(h, "AppData", "Roaming")
		}
		return filepath.Join(p, "AnimeCaos")
	}
	return filepath.Join(h, ".local", "state", "AnimeCaos")
}
func Binary(name string) (string, error) {
	ext := ""
	if runtime.GOOS == "windows" {
		ext = ".exe"
	}
	exe, _ := os.Executable()
	root := filepath.Dir(exe)
	for _, p := range []string{filepath.Join(root, "bin", name+ext), filepath.Join(root, name+ext), filepath.Join("bin", name+ext)} {
		if st, e := os.Stat(p); e == nil && !st.IsDir() {
			return filepath.Abs(p)
		}
	}
	if p, e := exec.LookPath(name); e == nil {
		return p, nil
	}
	return "", fmt.Errorf("%s não encontrado. Reinstale o pacote completo do AnimeCaos ou configure o PATH", name)
}
func Open(target string) error {
	var c *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		c = exec.Command("rundll32.exe", "url.dll,FileProtocolHandler", target)
	case "darwin":
		c = exec.Command("open", target)
	default:
		c = exec.Command("xdg-open", target)
	}
	Hide(c)
	if e := c.Start(); e != nil {
		return e
	}
	go c.Wait()
	return nil
}
func RevealFile(target string) error {
	return revealFileNative(target)
}
func SafeName(s string) string {
	s = strings.Map(func(r rune) rune {
		if r < 32 || strings.ContainsRune(`<>:"/\|?*`, r) {
			return '_'
		}
		return r
	}, s)
	s = strings.Trim(s, " .")
	if s == "" {
		s = "Sem título"
	}
	r := []rune(s)
	if len(r) > 100 {
		s = string(r[:100])
	}
	stem := strings.ToUpper(strings.Split(s, ".")[0])
	for _, n := range []string{"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"} {
		if stem == n {
			s = "_" + s
		}
	}
	return s
}
func Within(root, path string) bool {
	r, e := filepath.Abs(root)
	if e != nil {
		return false
	}
	p, e := filepath.Abs(path)
	if e != nil {
		return false
	}
	rel, e := filepath.Rel(r, p)
	return e == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator)) && !filepath.IsAbs(rel)
}
