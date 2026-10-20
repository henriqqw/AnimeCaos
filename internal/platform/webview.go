package platform

import (
	"os"
	"path/filepath"
)

func bundledWebView2Path(executable string) string {
	if executable == "" {
		return ""
	}
	root := filepath.Join(filepath.Dir(executable), "bin", "webview2")
	if info, err := os.Stat(filepath.Join(root, "msedgewebview2.exe")); err == nil && !info.IsDir() {
		return root
	}
	return ""
}
