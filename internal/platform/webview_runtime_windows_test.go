//go:build windows

package platform

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/wailsapp/go-webview2/webviewloader"
)

func TestBundledWebView2RuntimeVersion(t *testing.T) {
	runtimePath := os.Getenv("ANIMECAOS_WEBVIEW2_PATH")
	if runtimePath == "" {
		t.Skip("set ANIMECAOS_WEBVIEW2_PATH to validate the release bundle")
	}
	expected, err := os.ReadFile(filepath.Join(runtimePath, "version.txt"))
	if err != nil {
		t.Fatal(err)
	}
	actual, err := webviewloader.GetAvailableCoreWebView2BrowserVersionString(runtimePath)
	if err != nil {
		t.Fatalf("WebView2 loader rejected the bundled runtime: %v", err)
	}
	if strings.TrimSpace(actual) != strings.TrimSpace(string(expected)) {
		t.Fatalf("WebView2 version = %q, want %q", actual, strings.TrimSpace(string(expected)))
	}
}
