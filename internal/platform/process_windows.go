//go:build windows

package platform

import (
	"os/exec"
	"syscall"
)

func Hide(c *exec.Cmd) {
	c.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
}
