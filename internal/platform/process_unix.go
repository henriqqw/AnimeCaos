//go:build !windows

package platform

import "os/exec"

func HideConsole(c *exec.Cmd) {}

// WaitForProcessExit is only used by the Windows tray restart helper.
func WaitForProcessExit(int) error { return nil }
