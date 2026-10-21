// package builds a runtime-only distribution. It never copies the source tree,
// Python environment or yt-dlp into the output. Browser and media runtimes are
// staged explicitly so the installed application does not depend on PATH.
package main

import (
	"archive/zip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

type fileRecord struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
	Size   int64  `json:"size"`
}

func main() {
	if e := run(); e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
}
func command(dir, name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Dir = dir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}
func copyFile(src, dst string) error {
	in, e := os.Open(src)
	if e != nil {
		return e
	}
	defer in.Close()
	if e = os.MkdirAll(filepath.Dir(dst), 0755); e != nil {
		return e
	}
	out, e := os.OpenFile(dst, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0755)
	if e != nil {
		return e
	}
	_, e = io.Copy(out, in)
	ce := out.Close()
	if e != nil {
		return e
	}
	return ce
}

func copyTree(src, dst string) error {
	return filepath.WalkDir(src, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if path == src {
			return nil
		}
		rel, err := filepath.Rel(src, path)
		if err != nil {
			return err
		}
		target := filepath.Join(dst, rel)
		if entry.IsDir() {
			return os.MkdirAll(target, 0755)
		}
		if !entry.Type().IsRegular() {
			return fmt.Errorf("arquivo de licença não regular: %s", path)
		}
		return copyFile(path, target)
	})
}

func copyRuntimeTree(src, dst string) error {
	return filepath.WalkDir(src, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if path == src {
			return nil
		}
		rel, err := filepath.Rel(src, path)
		if err != nil {
			return err
		}
		target := filepath.Join(dst, rel)
		if entry.IsDir() {
			return os.MkdirAll(target, 0755)
		}
		if entry.Type()&os.ModeSymlink != 0 {
			link, err := os.Readlink(path)
			if err != nil {
				return err
			}
			if filepath.IsAbs(link) {
				return fmt.Errorf("link absoluto não permitido no runtime do Firefox: %s", path)
			}
			if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
				return err
			}
			return os.Symlink(link, target)
		}
		if !entry.Type().IsRegular() {
			return fmt.Errorf("arquivo de runtime não regular: %s", path)
		}
		return copyFile(path, target)
	})
}

func cleanPreviousStages(releaseDir, platform string) error {
	releaseRoot, err := filepath.Abs(releaseDir)
	if err != nil {
		return err
	}
	entries, err := os.ReadDir(releaseRoot)
	if err != nil {
		return err
	}
	prefix := "stage-" + platform + "-"
	for _, entry := range entries {
		if !entry.IsDir() || !strings.HasPrefix(entry.Name(), prefix) {
			continue
		}
		target := filepath.Join(releaseRoot, entry.Name())
		targetAbs, err := filepath.Abs(target)
		if err != nil {
			return err
		}
		relative, err := filepath.Rel(releaseRoot, targetAbs)
		if err != nil || relative == "." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) || filepath.IsAbs(relative) {
			return fmt.Errorf("stage antigo fora de release: %s", targetAbs)
		}
		if err := os.RemoveAll(targetAbs); err != nil {
			return fmt.Errorf("remover stage antigo %s: %w", targetAbs, err)
		}
	}
	return nil
}

func replaceChecksumEntry(releaseDir, filename, entry string) error {
	path := filepath.Join(releaseDir, "SHA256SUMS")
	content, err := os.ReadFile(path)
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	lines := strings.Split(string(content), "\n")
	filtered := make([]string, 0, len(lines)+1)
	for _, line := range lines {
		fields := strings.Fields(line)
		if len(fields) > 1 && filepath.Base(fields[len(fields)-1]) == filename {
			continue
		}
		if strings.TrimSpace(line) != "" {
			filtered = append(filtered, line)
		}
	}
	filtered = append(filtered, strings.TrimSpace(entry))
	return os.WriteFile(path, []byte(strings.Join(filtered, "\n")+"\n"), 0644)
}

func removeChecksumEntry(releaseDir, filename string) error {
	path := filepath.Join(releaseDir, "SHA256SUMS")
	content, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	lines := strings.Split(string(content), "\n")
	filtered := make([]string, 0, len(lines))
	for _, line := range lines {
		fields := strings.Fields(line)
		if len(fields) > 1 && filepath.Base(fields[len(fields)-1]) == filename {
			continue
		}
		if strings.TrimSpace(line) != "" {
			filtered = append(filtered, line)
		}
	}
	if len(filtered) == 0 {
		return os.Remove(path)
	}
	return os.WriteFile(path, []byte(strings.Join(filtered, "\n")+"\n"), 0644)
}

func replaceReleaseFile(releaseDir, filename string) error {
	if filepath.Base(filename) != filename {
		return fmt.Errorf("arquivo de release inválido: %s", filename)
	}
	releaseRoot, err := filepath.Abs(releaseDir)
	if err != nil {
		return err
	}
	target, err := filepath.Abs(filepath.Join(releaseRoot, filename))
	if err != nil {
		return err
	}
	if filepath.Dir(target) != releaseRoot {
		return fmt.Errorf("arquivo de release fora do diretório: %s", target)
	}
	if err := os.Remove(target); err != nil && !os.IsNotExist(err) {
		return err
	}
	return removeChecksumEntry(releaseDir, filename)
}

func runtimeVersion(path string, args ...string) (string, error) {
	output, err := exec.Command(path, args...).CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("consultar versão de %s: %w (%s)", path, err, strings.TrimSpace(string(output)))
	}
	return strings.TrimSpace(string(output)), nil
}

func buildDesktopExecutable(root, output, tags, ldflags string) error {
	if runtime.GOOS != "windows" {
		return command(root, "go", "build", "-trimpath", "-tags", tags, "-ldflags", ldflags, "-o", output, ".")
	}

	// Wails creates the Windows PE resources (application icon, manifest and
	// version metadata) during its build. A plain `go build` skips that step,
	// leaving the packaged executable with Windows' generic icon.
	wailsVersion, err := runtimeVersion("go", "list", "-m", "-f={{.Version}}", "github.com/wailsapp/wails/v2")
	if err != nil {
		return fmt.Errorf("consultar a versão do Wails para incorporar o ícone: %w", err)
	}
	if !strings.HasPrefix(wailsVersion, "v") {
		return fmt.Errorf("versão do Wails inválida: %s", wailsVersion)
	}

	outputName := filepath.Base(output)
	wailsOutput := filepath.Join(root, "build", "bin", outputName)
	if err := os.Remove(wailsOutput); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("remover executável Wails anterior: %w", err)
	}
	args := []string{
		"run", "github.com/wailsapp/wails/v2/cmd/wails@" + wailsVersion,
		"build", "-m", "-s", "-skipbindings", "-skipembedcreate",
		"-platform", runtime.GOOS + "/" + runtime.GOARCH,
		"-tags", tags,
		"-ldflags", ldflags,
		"-trimpath",
		"-o", outputName,
	}
	if err := command(root, "go", args...); err != nil {
		return fmt.Errorf("compilar executável Windows com os recursos Wails: %w", err)
	}
	if _, err := os.Stat(wailsOutput); err != nil {
		return fmt.Errorf("Wails não gerou %s: %w", wailsOutput, err)
	}
	if err := copyFile(wailsOutput, output); err != nil {
		return fmt.Errorf("copiar executável Windows com ícone: %w", err)
	}
	return nil
}

func run() error {
	version := flag.String("version", "3.0.2", "version")
	skipUI := flag.Bool("skip-ui", false, "reuse compiled frontend")
	flag.Parse()
	root, e := os.Getwd()
	if e != nil {
		return e
	}
	if _, e = os.Stat(filepath.Join(root, "wails.json")); e != nil {
		return fmt.Errorf("execute na raiz do repositório")
	}
	if strings.ContainsAny(*version, "/\\:") {
		return fmt.Errorf("versão inválida")
	}
	if !*skipUI {
		npm := "npm"
		if runtime.GOOS == "windows" {
			npm = "npm.cmd"
		}
		if e = command(filepath.Join(root, "frontend"), npm, "ci"); e != nil {
			return e
		}
		if e = command(filepath.Join(root, "frontend"), npm, "run", "build"); e != nil {
			return e
		}
	}
	release := filepath.Join(root, "release")
	if e = os.MkdirAll(release, 0755); e != nil {
		return e
	}
	if e = cleanPreviousStages(release, runtime.GOOS); e != nil {
		return e
	}
	if runtime.GOOS == "windows" {
		for _, name := range []string{
			"AnimeCaos-" + *version + "-windows-" + runtime.GOARCH + ".zip",
			"AnimeCaos-" + *version + "-windows-setup.exe",
		} {
			if e = replaceReleaseFile(release, name); e != nil {
				return fmt.Errorf("remover pacote anterior %s: %w", name, e)
			}
		}
	}
	stage, e := os.MkdirTemp(release, "stage-"+runtime.GOOS+"-*")
	if e != nil {
		return e
	}
	ext := ""
	if runtime.GOOS == "windows" {
		ext = ".exe"
	}
	tags := "desktop,production"
	ldflags := "-s -w -X github.com/henriqqw/animecaos/internal/update.Version=" + *version
	if runtime.GOOS == "windows" {
		ldflags += " -H windowsgui"
	} else {
		tags += ",webkit2_41"
	}
	if e = buildDesktopExecutable(root, filepath.Join(stage, "AnimeCaos"+ext), tags, ldflags); e != nil {
		return e
	}
	if e = command(root, "go", "build", "-trimpath", "-ldflags", "-s -w -X github.com/henriqqw/animecaos/internal/update.Version="+*version, "-o", filepath.Join(stage, "animecaos-cli"+ext), "./cmd/animecaos"); e != nil {
		return e
	}
	for _, name := range []string{"mpv", "ffmpeg", "ffprobe"} {
		src := filepath.Join(root, "bin", name+ext)
		if _, e = os.Stat(src); e != nil {
			return fmt.Errorf("runtime %s ausente em bin/: %w", name, e)
		}
		if e = copyFile(src, filepath.Join(stage, "bin", name+ext)); e != nil {
			return e
		}
	}
	// The scraper uses Firefox/WebDriver when an embed requires JavaScript.
	// Both components are mandatory in release packages; system-installed
	// browsers are development fallbacks only and must not mask an incomplete
	// release stage.
	firefoxRoot := strings.TrimSpace(os.Getenv("ANIMECAOS_FIREFOX_BUNDLE_DIR"))
	if firefoxRoot == "" {
		firefoxRoot = filepath.Join(root, "bin", "firefox")
	}
	firefoxName := "firefox"
	geckoName := "geckodriver"
	if runtime.GOOS == "windows" {
		firefoxName += ".exe"
		geckoName += ".exe"
	}
	if _, e = os.Stat(filepath.Join(firefoxRoot, firefoxName)); e != nil {
		return fmt.Errorf("Firefox empacotável ausente (%s): %w", filepath.Join(firefoxRoot, firefoxName), e)
	}
	geckoPath := strings.TrimSpace(os.Getenv("ANIMECAOS_GECKODRIVER_BUNDLE_PATH"))
	if geckoPath == "" {
		geckoPath = filepath.Join(root, "bin", geckoName)
	}
	if _, e = os.Stat(geckoPath); e != nil {
		return fmt.Errorf("GeckoDriver empacotável ausente (%s): %w", geckoPath, e)
	}
	if e = copyRuntimeTree(firefoxRoot, filepath.Join(stage, "bin", "firefox")); e != nil {
		return fmt.Errorf("copiar Firefox: %w", e)
	}
	if e = copyFile(geckoPath, filepath.Join(stage, "bin", geckoName)); e != nil {
		return fmt.Errorf("copiar GeckoDriver: %w", e)
	}
	// mpv may be shipped with runtime DLLs alongside mpv.exe. Keep those beside
	// the executable, where Windows' loader and the MPV IPC client can resolve them.
	if runtime.GOOS == "windows" {
		entries, readErr := os.ReadDir(filepath.Join(root, "bin"))
		if readErr != nil {
			return readErr
		}
		for _, entry := range entries {
			if entry.IsDir() || !strings.EqualFold(filepath.Ext(entry.Name()), ".dll") {
				continue
			}
			if e = copyFile(filepath.Join(root, "bin", entry.Name()), filepath.Join(stage, "bin", entry.Name())); e != nil {
				return e
			}
		}
	}
	for _, name := range []string{"icon.ico", "icon.png"} {
		src := filepath.Join(root, "public", name)
		if _, e = os.Stat(src); e == nil {
			if e = copyFile(src, filepath.Join(stage, name)); e != nil {
				return e
			}
		}
	}
	if runtime.GOOS == "windows" {
		webviewRoot := filepath.Join(root, "bin", "webview2")
		if _, e = os.Stat(filepath.Join(webviewRoot, "msedgewebview2.exe")); e != nil {
			return fmt.Errorf("runtime WebView2 fixo ausente em bin/webview2: %w", e)
		}
		if e = copyRuntimeTree(webviewRoot, filepath.Join(stage, "bin", "webview2")); e != nil {
			return fmt.Errorf("copiar runtime WebView2 fixo: %w", e)
		}
		webviewVersion, readErr := os.ReadFile(filepath.Join(webviewRoot, "version.txt"))
		if readErr != nil {
			return fmt.Errorf("ler versão fixada do WebView2: %w", readErr)
		}
		if strings.TrimSpace(string(webviewVersion)) == "" {
			return fmt.Errorf("versão fixada do WebView2 vazia em bin/webview2/version.txt")
		}
		if e = os.MkdirAll(filepath.Join(stage, "licenses", "media"), 0755); e != nil {
			return e
		}
		if e = os.WriteFile(filepath.Join(stage, "licenses", "media", "webview2-runtime-version.txt"), webviewVersion, 0644); e != nil {
			return e
		}
	}
	if e = copyFile(filepath.Join(root, "docs", "DISTRIBUTION.md"), filepath.Join(stage, "DISTRIBUTION.md")); e != nil {
		return e
	}
	if e = copyFile(filepath.Join(root, "THIRD-PARTY-NOTICES.md"), filepath.Join(stage, "THIRD-PARTY-NOTICES.md")); e != nil {
		return e
	}
	licenseDir := filepath.Join(root, "licenses")
	if _, e = os.Stat(licenseDir); e != nil {
		return fmt.Errorf("diretório de licenças obrigatório ausente: %w", e)
	}
	if e = copyTree(licenseDir, filepath.Join(stage, "licenses")); e != nil {
		return e
	}
	for _, relative := range []string{filepath.Join("media", "firefox", "MPL-2.0.txt"), filepath.Join("media", "geckodriver", "MPL-2.0.txt")} {
		if _, e = os.Stat(filepath.Join(stage, "licenses", relative)); e != nil {
			return fmt.Errorf("licença obrigatória do runtime ausente (%s): %w", relative, e)
		}
	}
	firefoxVersion, e := runtimeVersion(filepath.Join(stage, "bin", "firefox", firefoxName), "--version")
	if e != nil {
		return e
	}
	geckoVersion, e := runtimeVersion(filepath.Join(stage, "bin", geckoName), "--version")
	if e != nil {
		return e
	}
	if e = os.MkdirAll(filepath.Join(stage, "licenses", "media"), 0755); e != nil {
		return e
	}
	if e = os.WriteFile(filepath.Join(stage, "licenses", "media", "browser-runtime-versions.txt"), []byte(firefoxVersion+"\n"+geckoVersion+"\n"), 0644); e != nil {
		return e
	}
	files := []fileRecord{}
	e = filepath.WalkDir(stage, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		relative, _ := filepath.Rel(stage, path)
		lower := strings.ToLower(relative)
		if strings.HasSuffix(lower, ".py") || strings.Contains(lower, "yt-dlp") {
			return fmt.Errorf("dependência proibida na distribuição: %s", relative)
		}
		f, e := os.Open(path)
		if e != nil {
			return e
		}
		defer f.Close()
		h := sha256.New()
		size, e := io.Copy(h, f)
		if e != nil {
			return e
		}
		files = append(files, fileRecord{filepath.ToSlash(relative), hex.EncodeToString(h.Sum(nil)), size})
		return nil
	})
	if e != nil {
		return e
	}
	manifest, e := json.MarshalIndent(map[string]any{"version": *version, "platform": runtime.GOOS, "arch": runtime.GOARCH, "created": time.Now().UTC().Format(time.RFC3339), "files": files}, "", "  ")
	if e != nil {
		return e
	}
	if e = os.WriteFile(filepath.Join(stage, "release-manifest.json"), manifest, 0644); e != nil {
		return e
	}
	if runtime.GOOS != "windows" {
		fmt.Println("AppDir input:", stage)
		return nil
	}
	dest := filepath.Join(release, "AnimeCaos-"+*version+"-windows-"+runtime.GOARCH+".zip")
	f, e := os.OpenFile(dest, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0644)
	if e != nil {
		return e
	}
	z := zip.NewWriter(f)
	e = filepath.WalkDir(stage, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		rel, _ := filepath.Rel(stage, path)
		w, e := z.Create(filepath.ToSlash(rel))
		if e != nil {
			return e
		}
		r, e := os.Open(path)
		if e != nil {
			return e
		}
		defer r.Close()
		_, e = io.Copy(w, r)
		return e
	})
	ze := z.Close()
	fe := f.Close()
	if e != nil {
		return e
	}
	if ze != nil {
		return ze
	}
	if fe != nil {
		return fe
	}
	f, e = os.Open(dest)
	if e != nil {
		return e
	}
	h := sha256.New()
	_, e = io.Copy(h, f)
	f.Close()
	if e != nil {
		return e
	}
	sum := hex.EncodeToString(h.Sum(nil)) + "  " + filepath.Base(dest)
	if e = replaceChecksumEntry(release, filepath.Base(dest), sum); e != nil {
		return e
	}
	fmt.Println("Portable:", dest)
	fmt.Println("Installer input:", stage)
	return nil
}
