// package builds a runtime-only distribution. It never copies the source tree,
// Python environment, Selenium, geckodriver or yt-dlp into the output.
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
func run() error {
	version := flag.String("version", "3.0.0-dev", "version")
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
	if e = command(root, "go", "build", "-trimpath", "-tags", tags, "-ldflags", ldflags, "-o", filepath.Join(stage, "AnimeCaos"+ext), "."); e != nil {
		return e
	}
	if e = command(root, "go", "build", "-trimpath", "-ldflags", "-s -w -X github.com/henriqqw/animecaos/internal/update.Version="+*version, "-o", filepath.Join(stage, "animecaos-cli"+ext), "./cmd/animecaos"); e != nil {
		return e
	}
	for _, name := range []string{"mpv", "ffmpeg", "ffprobe"} {
		src := filepath.Join(root, "bin", name+ext)
		if _, e = os.Stat(src); e != nil {
			src, e = exec.LookPath(name)
			if e != nil {
				return fmt.Errorf("dependência %s: %w", name, e)
			}
		}
		if e = copyFile(src, filepath.Join(stage, "bin", name+ext)); e != nil {
			return e
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
		bootstrap := filepath.Join(root, "bin", "MicrosoftEdgeWebview2Setup.exe")
		if _, e = os.Stat(bootstrap); e == nil {
			if e = copyFile(bootstrap, filepath.Join(stage, "bin", "MicrosoftEdgeWebview2Setup.exe")); e != nil {
				return e
			}
		} else {
			fmt.Fprintln(os.Stderr, "WebView2 bootstrap ausente: portátil requer runtime instalado")
		}
	}
	if e = copyFile(filepath.Join(root, "docs", "DISTRIBUTION.md"), filepath.Join(stage, "DISTRIBUTION.md")); e != nil {
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
		if strings.HasSuffix(lower, ".py") || strings.Contains(lower, "yt-dlp") || strings.Contains(lower, "geckodriver") {
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
	sum := hex.EncodeToString(h.Sum(nil)) + "  " + filepath.Base(dest) + "\n"
	sf, e := os.OpenFile(filepath.Join(release, "SHA256SUMS"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if e != nil {
		return e
	}
	_, e = sf.WriteString(sum)
	sf.Close()
	if e != nil {
		return e
	}
	fmt.Println("Portable:", dest)
	fmt.Println("Installer input:", stage)
	return nil
}
