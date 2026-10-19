//go:build !windows

package update

import (
	"fmt"
	"syscall"
	"time"
)

func waitParent(pid int, timeout time.Duration) error {
	if pid <= 0 {
		return fmt.Errorf("processo pai inválido")
	}
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if e := syscall.Kill(pid, 0); e == syscall.ESRCH {
			return nil
		}
		time.Sleep(100 * time.Millisecond)
	}
	return fmt.Errorf("aplicativo ainda em execução")
}
