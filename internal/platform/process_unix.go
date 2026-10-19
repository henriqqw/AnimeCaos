//go:build !windows

package platform

import "os/exec"

func Hide(c *exec.Cmd) {}
