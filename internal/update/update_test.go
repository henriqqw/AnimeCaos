package update

import (
	"archive/zip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/henriqqw/animecaos/internal/netx"
	"net/http"
	"net/http/httptest"
)

func TestVersionComparison(t *testing.T) {
	for _, v := range []struct {
		a, b string
		want bool
	}{{"v3.0.0", "3.0.0-dev", true}, {"3.0.1", "3.0.0", true}, {"2.9.9", "3.0.0", false}, {"3.0.0", "3.0.0", false}, {"4.0.0", "3.9.9", true}} {
		if Newer(v.a, v.b) != v.want {
			t.Fatalf("%s %s", v.a, v.b)
		}
	}
}
func TestStageRejectsTraversal(t *testing.T) {
	for _, name := range []string{"../outside", "dir/../../outside"} {
		dir := t.TempDir()
		file := filepath.Join(dir, "package.zip")
		f, _ := os.Create(file)
		z := zip.NewWriter(f)
		w, _ := z.Create(name)
		w.Write([]byte("evil"))
		z.Close()
		f.Close()
		if Stage(file, filepath.Join(dir, "staged")) == nil {
			t.Fatalf("accepted %s", name)
		}
		if _, e := os.Stat(filepath.Join(dir, "outside")); !os.IsNotExist(e) {
			t.Fatal("escaped extraction directory")
		}
	}
}

func TestDownloadChecksReleaseChecksumBeforePublishing(t *testing.T) {
	payload := []byte("signed-by-checksum-release-payload")
	digest := sha256.Sum256(payload)
	artifactName := "AnimeCaos-3.1.0-windows-amd64.zip"
	if runtime.GOOS == "linux" {
		artifactName = "AnimeCaos-3.1.0-x86_64.AppImage"
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/latest":
			json.NewEncoder(w).Encode(map[string]any{"tag_name": "v3.1.0", "assets": []any{
				map[string]string{"name": "SHA256SUMS", "browser_download_url": serverURL(r, "/checksums")},
				map[string]string{"name": artifactName, "browser_download_url": serverURL(r, "/package")},
			}})
		case "/checksums":
			fmt.Fprintf(w, "%s  %s\n", hex.EncodeToString(digest[:]), artifactName)
		case "/package":
			w.Write(payload)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	client := netx.New()
	client.HTTP = server.Client()
	service := New(client)
	service.API = server.URL + "/latest"
	info, err := service.Check(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if !info.Available || info.Name != artifactName {
		t.Fatalf("unexpected release selection: %+v", info)
	}
	path, err := service.Download(context.Background(), info, t.TempDir(), func(int) {})
	if err != nil {
		t.Fatal(err)
	}
	got, err := os.ReadFile(path)
	if err != nil || string(got) != string(payload) {
		t.Fatalf("downloaded payload = %q, err=%v", got, err)
	}
}

func TestDownloadRejectsChecksumMismatch(t *testing.T) {
	payload := []byte("tampered")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/checksums":
			fmt.Fprintln(w, strings.Repeat("0", 64)+"  package.zip")
		case "/package":
			w.Write(payload)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	client := netx.New()
	client.HTTP = server.Client()
	service := New(client)
	info := Info{Available: true, URL: server.URL + "/package", ChecksumURL: server.URL + "/checksums", Name: "package.zip"}
	dir := t.TempDir()
	if _, err := service.Download(context.Background(), info, dir, func(int) {}); err == nil {
		t.Fatal("accepted a package with a mismatched checksum")
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 0 {
		t.Fatalf("checksum-failed download left files behind: %v", entries)
	}
}

func TestApplyHelperRunsFromOutsideInstallDirectory(t *testing.T) {
	root := t.TempDir()
	target := filepath.Join(root, "installed")
	cmd := newApplyCommand("updater", filepath.Join(root, "updates", "package.zip"), target, 42)
	if got, want := filepath.Clean(cmd.Dir), filepath.Clean(root); got != want {
		t.Fatalf("helper working directory = %q, want installation parent %q", got, want)
	}
}

func TestUpdateHelperCleansIncompleteStage(t *testing.T) {
	root := t.TempDir()
	target := filepath.Join(root, "installed")
	if err := os.MkdirAll(target, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(target, "AnimeCaos.exe"), []byte("old-app"), 0755); err != nil {
		t.Fatal(err)
	}
	packagePath := writeUpdateZip(t, root, map[string][]byte{"README.txt": []byte("incomplete package")})
	if err := runHelper(packagePath, target, 2147483647, func(string) error { return nil }); err == nil {
		t.Fatal("incomplete package was accepted")
	}
	entries, err := os.ReadDir(root)
	if err != nil {
		t.Fatal(err)
	}
	for _, entry := range entries {
		if strings.HasPrefix(entry.Name(), ".animecaos-update-") {
			t.Fatalf("failed update left staging directory %q", entry.Name())
		}
	}
}

func TestUpdateHelperReplacesApplicationAndPreservesUserData(t *testing.T) {
	root := t.TempDir()
	target := filepath.Join(root, "installed")
	if err := os.MkdirAll(target, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(target, "AnimeCaos.exe"), []byte("old-app"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(target, "unins000.exe"), []byte("installer-record"), 0755); err != nil {
		t.Fatal(err)
	}
	dataDir := filepath.Join(root, "user-data")
	if err := os.MkdirAll(dataDir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dataDir, "state.db"), []byte("user-progress"), 0600); err != nil {
		t.Fatal(err)
	}
	packagePath := writeUpdateZip(t, root, map[string][]byte{
		"AnimeCaos.exe":         []byte("new-app"),
		"release-manifest.json": []byte(`{"version":"3.1.0"}`),
		"bin/mpv.exe":           []byte("new-mpv"),
	})
	if err := runHelper(packagePath, target, 2147483647, func(string) error { return nil }); err != nil {
		t.Fatal(err)
	}
	if got, err := os.ReadFile(filepath.Join(target, "AnimeCaos.exe")); err != nil || string(got) != "new-app" {
		t.Fatalf("updated app = %q, err=%v", got, err)
	}
	if got, err := os.ReadFile(filepath.Join(target, "unins000.exe")); err != nil || string(got) != "installer-record" {
		t.Fatalf("uninstaller record was not preserved: %q, err=%v", got, err)
	}
	if got, err := os.ReadFile(filepath.Join(dataDir, "state.db")); err != nil || string(got) != "user-progress" {
		t.Fatalf("user data changed during update: %q, err=%v", got, err)
	}
}

func TestUpdateHelperRollsBackWhenUpdatedAppCannotStart(t *testing.T) {
	root := t.TempDir()
	target := filepath.Join(root, "installed")
	if err := os.MkdirAll(target, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(target, "AnimeCaos.exe"), []byte("old-app"), 0755); err != nil {
		t.Fatal(err)
	}
	packagePath := writeUpdateZip(t, root, map[string][]byte{
		"AnimeCaos.exe":         []byte("new-app"),
		"release-manifest.json": []byte(`{"version":"3.1.0"}`),
	})
	launchErr := errors.New("startup failed")
	if err := runHelper(packagePath, target, 2147483647, func(string) error { return launchErr }); !errors.Is(err, launchErr) {
		t.Fatalf("update error = %v, want startup failure", err)
	}
	if got, err := os.ReadFile(filepath.Join(target, "AnimeCaos.exe")); err != nil || string(got) != "old-app" {
		t.Fatalf("previous app was not restored: %q, err=%v", got, err)
	}
}

func writeUpdateZip(t *testing.T, dir string, files map[string][]byte) string {
	t.Helper()
	path := filepath.Join(dir, "update.zip")
	file, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	archive := zip.NewWriter(file)
	for name, content := range files {
		entry, err := archive.Create(name)
		if err != nil {
			t.Fatal(err)
		}
		if _, err = entry.Write(content); err != nil {
			t.Fatal(err)
		}
	}
	if err := archive.Close(); err != nil {
		t.Fatal(err)
	}
	if err := file.Close(); err != nil {
		t.Fatal(err)
	}
	return path
}

func serverURL(r *http.Request, path string) string {
	return "http://" + r.Host + path
}
