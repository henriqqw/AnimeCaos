package update

import (
	"archive/zip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/platform"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
)

var Version = "3.0.5"

type Info struct {
	Version     string `json:"version"`
	Notes       string `json:"notes"`
	URL         string `json:"url"`
	Name        string `json:"name"`
	ChecksumURL string `json:"checksumUrl"`
	Available   bool   `json:"available"`
	Managed     bool   `json:"managed"`
}
type Service struct {
	Client *netx.Client
	API    string
}

func New(c *netx.Client) *Service {
	return &Service{c, "https://api.github.com/repos/henriqqw/animecaos/releases/latest"}
}
func Newer(latest, current string) bool {
	parse := func(s string) [3]int {
		var v [3]int
		for i, p := range strings.Split(strings.Split(strings.TrimPrefix(s, "v"), "-")[0], ".") {
			if i > 2 {
				break
			}
			v[i], _ = strconv.Atoi(p)
		}
		return v
	}
	a, b := parse(latest), parse(current)
	for i := 0; i < 3; i++ {
		if a[i] != b[i] {
			return a[i] > b[i]
		}
	}
	return strings.Contains(current, "-") && !strings.Contains(latest, "-")
}
func (s *Service) Check(ctx context.Context) (Info, error) {
	out := Info{Version: Version, Managed: os.Getenv("FLATPAK_ID") != ""}
	var r struct {
		Tag    string `json:"tag_name"`
		Body   string `json:"body"`
		Assets []struct {
			Name string `json:"name"`
			URL  string `json:"browser_download_url"`
		} `json:"assets"`
	}
	if e := s.Client.JSON(ctx, "GET", s.API, nil, nil, &r); e != nil {
		return out, e
	}
	out.Version = strings.TrimPrefix(r.Tag, "v")
	out.Notes = r.Body
	for _, a := range r.Assets {
		if a.Name == "SHA256SUMS" {
			out.ChecksumURL = a.URL
		}
		if runtime.GOOS == "windows" && strings.HasSuffix(a.Name, "windows-amd64.zip") || runtime.GOOS == "linux" && strings.HasSuffix(a.Name, "x86_64.AppImage") {
			out.URL = a.URL
			out.Name = a.Name
		}
	}
	out.Available = Newer(out.Version, Version) && out.URL != ""
	return out, nil
}
func (s *Service) Download(ctx context.Context, info Info, dir string, progress func(int)) (string, error) {
	if !info.Available || info.Managed {
		return "", fmt.Errorf("atualização indisponível ou gerenciada pelo Flatpak")
	}
	if info.ChecksumURL == "" {
		return "", fmt.Errorf("release sem SHA256SUMS; atualização não aplicada")
	}
	r, e := s.Client.Do(ctx, "GET", info.ChecksumURL, nil, nil)
	if e != nil {
		return "", e
	}
	checks, e := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	r.Body.Close()
	if e != nil {
		return "", e
	}
	want := ""
	for _, line := range strings.Split(string(checks), "\n") {
		f := strings.Fields(line)
		if len(f) >= 2 && strings.TrimPrefix(f[1], "*") == info.Name {
			want = f[0]
		}
	}
	if len(want) != 64 {
		return "", fmt.Errorf("checksum do pacote não encontrado")
	}
	if e = os.MkdirAll(dir, 0700); e != nil {
		return "", e
	}
	f, e := os.CreateTemp(dir, "update-*.part")
	if e != nil {
		return "", e
	}
	tmp := f.Name()
	defer os.Remove(tmp)
	defer f.Close()
	r, e = s.Client.Stream(ctx, info.URL, nil)
	if e != nil {
		return "", e
	}
	defer r.Body.Close()
	h := sha256.New()
	buf := make([]byte, 128<<10)
	var count int64
	for {
		n, err := r.Body.Read(buf)
		if n > 0 {
			if _, e = io.MultiWriter(f, h).Write(buf[:n]); e != nil {
				return "", e
			}
			count += int64(n)
			if count > 2<<30 {
				return "", fmt.Errorf("pacote excede 2 GB")
			}
			if r.ContentLength > 0 {
				progress(int(count * 100 / r.ContentLength))
			}
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			return "", err
		}
	}
	if !strings.EqualFold(hex.EncodeToString(h.Sum(nil)), want) {
		return "", fmt.Errorf("checksum inválido; pacote descartado")
	}
	if e = f.Sync(); e != nil {
		return "", e
	}
	f.Close()
	dest := filepath.Join(dir, filepath.Base(info.Name))
	if e = os.Rename(tmp, dest); e != nil {
		return "", e
	}
	return dest, nil
}
func Stage(zipPath, dir string) error {
	z, e := zip.OpenReader(zipPath)
	if e != nil {
		return e
	}
	defer z.Close()
	seen := map[string]bool{}
	var total uint64
	for _, f := range z.File {
		if strings.ContainsAny(f.Name, "\\:\x00") {
			return fmt.Errorf("nome inválido no pacote")
		}
		p := filepath.Join(dir, filepath.FromSlash(f.Name))
		if !platform.Within(dir, p) || f.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("caminho inválido no pacote")
		}
		if f.FileInfo().IsDir() {
			if e = os.MkdirAll(p, 0755); e != nil {
				return e
			}
			continue
		}
		canonical := strings.ToLower(filepath.Clean(p))
		if seen[canonical] {
			return fmt.Errorf("arquivo duplicado no pacote")
		}
		seen[canonical] = true
		total += f.UncompressedSize64
		if total > 4<<30 {
			return fmt.Errorf("pacote descompactado excede 4 GB")
		}
		if f.UncompressedSize64 > 2<<30 {
			return fmt.Errorf("arquivo excessivamente grande")
		}
		if e = os.MkdirAll(filepath.Dir(p), 0755); e != nil {
			return e
		}
		r, e := f.Open()
		if e != nil {
			return e
		}
		w, e := os.OpenFile(p, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0755)
		if e != nil {
			r.Close()
			return e
		}
		_, e = io.Copy(w, io.LimitReader(r, 2<<30))
		r.Close()
		ce := w.Close()
		if e != nil {
			return e
		}
		if ce != nil {
			return ce
		}
	}
	return nil
}

// A copied helper waits for the parent to close; it only replaces files in the
// application directory, preserving user data. Existing binaries are backed up.
func Apply(helper, packagePath, target string, pid int) error {
	cmd := newApplyCommand(helper, packagePath, target, pid)
	return cmd.Start()
}

func newApplyCommand(helper, packagePath, target string, pid int) *exec.Cmd {
	cmd := exec.Command(helper, "--apply-update", packagePath, "--target", target, "--parent", strconv.Itoa(pid))
	// The helper must not inherit the application's working directory. On
	// Windows that directory is the install directory, and keeping it as the
	// helper's current directory prevents renaming the directory during update.
	cmd.Dir = filepath.Dir(filepath.Clean(target))
	platform.HideConsole(cmd)
	return cmd
}
func RunHelper(packagePath, target string, pid int) error {
	return runHelper(packagePath, target, pid, launchUpdatedApp)
}

func launchUpdatedApp(path string) error {
	cmd := exec.Command(path)
	platform.HideConsole(cmd)
	if err := cmd.Start(); err != nil {
		return err
	}
	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	timer := time.NewTimer(3 * time.Second)
	defer timer.Stop()
	select {
	case err := <-done:
		if err != nil {
			return fmt.Errorf("o aplicativo atualizado encerrou durante a inicialização: %w", err)
		}
		return fmt.Errorf("o aplicativo atualizado encerrou durante a inicialização")
	case <-timer.C:
		return nil
	}
}

func runHelper(packagePath, target string, pid int, launch func(string) error) error {
	if !filepath.IsAbs(target) || filepath.Clean(target) == filepath.VolumeName(target)+string(os.PathSeparator) {
		return fmt.Errorf("destino de atualização inválido")
	}
	if e := waitParent(pid, 60*time.Second); e != nil {
		return e
	}
	if e := prepareInstallDirectory(target); e != nil {
		return e
	}
	var e error
	backup := target + ".previous-" + time.Now().Format("20060102-150405")
	if strings.HasSuffix(packagePath, ".AppImage") {
		b, e := os.ReadFile(packagePath)
		if e != nil {
			return e
		}
		if len(b) < 4 || string(b[:4]) != "\x7fELF" {
			return fmt.Errorf("AppImage inválido")
		}
		f, err := os.CreateTemp(filepath.Dir(target), ".animecaos-new-*")
		if err != nil {
			return err
		}
		tmp := f.Name()
		defer os.Remove(tmp)
		if _, e = f.Write(b); e != nil {
			f.Close()
			return e
		}
		if e = f.Close(); e != nil {
			return e
		}
		if e = os.Chmod(tmp, 0755); e != nil {
			return e
		}
		if e = os.Rename(target, backup); e != nil {
			return e
		}
		if e = os.Rename(tmp, target); e != nil {
			os.Rename(backup, target)
			return e
		}
		if e = launch(target); e != nil {
			os.Rename(target, target+".failed")
			os.Rename(backup, target)
			return e
		}
		return nil
	}
	if _, e = os.Stat(filepath.Join(target, "AnimeCaos.exe")); e != nil {
		return fmt.Errorf("pasta de aplicativo não reconhecida: %w", e)
	}
	stage, e := os.MkdirTemp(filepath.Dir(target), ".animecaos-update-*")
	if e != nil {
		return e
	}
	defer os.RemoveAll(stage)
	if e = Stage(packagePath, stage); e != nil {
		return e
	}
	for _, name := range []string{"AnimeCaos.exe", "release-manifest.json"} {
		if _, e = os.Stat(filepath.Join(stage, name)); e != nil {
			return fmt.Errorf("pacote incompleto: %s", name)
		}
	}
	// Preserve Inno Setup's uninstall records when updating an installed copy.
	entries, e := os.ReadDir(target)
	if e != nil {
		return e
	}
	for _, entry := range entries {
		name := entry.Name()
		if entry.IsDir() || !strings.HasPrefix(strings.ToLower(name), "unins") || (filepath.Ext(name) != ".exe" && filepath.Ext(name) != ".dat" && filepath.Ext(name) != ".msg") {
			continue
		}
		src, e := os.Open(filepath.Join(target, name))
		if e != nil {
			return e
		}
		dst, e := os.OpenFile(filepath.Join(stage, name), os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0755)
		if e != nil {
			src.Close()
			return e
		}
		_, e = io.Copy(dst, src)
		src.Close()
		ce := dst.Close()
		if e != nil {
			return e
		}
		if ce != nil {
			return ce
		}
	}
	if _, e := os.Stat(backup); e == nil {
		return fmt.Errorf("backup de atualização já existe: %s", backup)
	}
	if e = os.Rename(target, backup); e != nil {
		return e
	}
	if e = os.Rename(stage, target); e != nil {
		os.Rename(backup, target)
		return e
	}
	if e = launch(filepath.Join(target, "AnimeCaos.exe")); e != nil {
		os.Rename(target, target+".failed")
		os.Rename(backup, target)
		return e
	}
	return nil
}
