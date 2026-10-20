package platform

import (
	"os"
	"path/filepath"
	"testing"
)

func TestBundledWebView2PathRequiresRuntimeExecutable(t *testing.T) {
	root := t.TempDir()
	executable := filepath.Join(root, "AnimeCaos.exe")
	runtimeDir := filepath.Join(root, "bin", "webview2")
	if got := bundledWebView2Path(executable); got != "" {
		t.Fatalf("returned a runtime path before its executable existed: %q", got)
	}
	if err := os.MkdirAll(runtimeDir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(runtimeDir, "msedgewebview2.exe"), []byte("runtime"), 0644); err != nil {
		t.Fatal(err)
	}
	if got := bundledWebView2Path(executable); got != runtimeDir {
		t.Fatalf("runtime path = %q, want %q", got, runtimeDir)
	}
}
