//go:build windows

package platform

import (
	"errors"
	"os/exec"
	"syscall"

	"golang.org/x/sys/windows"
)

func Hide(c *exec.Cmd) {
	c.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
}

// HideConsole prevents console-subsystem tools from opening a console while
// leaving GUI windows created by the child process visible. HideWindow also
// sets STARTF_USESHOWWINDOW/SW_HIDE and can hide a GUI child's initial window.
func HideConsole(c *exec.Cmd) {
	c.SysProcAttr = &syscall.SysProcAttr{CreationFlags: 0x08000000}
}

// WaitForProcessExit lets a restart helper wait until the current app releases
// its single-instance mutex before starting the replacement process.
func WaitForProcessExit(pid int) error {
	process, err := windows.OpenProcess(windows.SYNCHRONIZE, false, uint32(pid))
	if errors.Is(err, windows.ERROR_INVALID_PARAMETER) {
		return nil
	}
	if err != nil {
		return err
	}
	defer windows.CloseHandle(process)
	_, err = windows.WaitForSingleObject(process, windows.INFINITE)
	return err
}
