//go:build windows

package platform

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/wailsapp/wails/v2/pkg/options/windows"
)

func WebViewOptions() (*windows.Options, error) {
	executable, err := os.Executable()
	if err != nil {
		return nil, fmt.Errorf("localizar executável do AnimeCaos: %w", err)
	}
	path := bundledWebView2Path(executable)
	if path == "" {
		// Development runs continue to use the WebView2 installed on the machine.
		return nil, nil
	}

	marker := filepath.Join(path, ".animecaos-appcontainer-acl-v1")
	if _, err := os.Stat(marker); err != nil {
		cmd := exec.Command("icacls.exe", path,
			"/grant", "*S-1-15-2-2:(OI)(CI)(RX)", "*S-1-15-2-1:(OI)(CI)(RX)",
			"/T", "/C")
		HideConsole(cmd)
		if output, runErr := cmd.CombinedOutput(); runErr != nil {
			return nil, fmt.Errorf("configurar acesso do WebView2 empacotado: %w (%s)", runErr, string(output))
		}
		if err = os.WriteFile(marker, []byte("ok\n"), 0600); err != nil {
			return nil, fmt.Errorf("registrar permissões do WebView2 empacotado: %w", err)
		}
	}
	return &windows.Options{WebviewBrowserPath: path}, nil
}
