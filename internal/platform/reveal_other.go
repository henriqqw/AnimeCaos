//go:build !windows

package platform

import (
	"fmt"
	"os/exec"
	"path/filepath"
	"runtime"
)

func revealFileNative(target string) error {
	var command *exec.Cmd
	if runtime.GOOS == "darwin" {
		command = exec.Command("open", "-R", target)
	} else {
		command = exec.Command("xdg-open", filepath.Dir(target))
	}
	Hide(command)
	if err := command.Run(); err != nil {
		return fmt.Errorf("não foi possível abrir a pasta do arquivo: %w", err)
	}
	return nil
}
