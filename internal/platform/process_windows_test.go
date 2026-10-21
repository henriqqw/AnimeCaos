//go:build windows

package platform

import (
	"os/exec"
	"testing"
)

func TestHideConsoleKeepsGUIWindowVisible(t *testing.T) {
	command := exec.Command("AnimeCaos.exe")
	HideConsole(command)
	if command.SysProcAttr == nil {
		t.Fatal("HideConsole did not configure process attributes")
	}
	if command.SysProcAttr.HideWindow {
		t.Fatal("HideConsole must not set STARTF_USESHOWWINDOW/SW_HIDE for GUI children")
	}
	if command.SysProcAttr.CreationFlags&0x08000000 == 0 {
		t.Fatal("HideConsole must set CREATE_NO_WINDOW to suppress console windows")
	}
}
