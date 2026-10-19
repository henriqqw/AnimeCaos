//go:build windows

package update

import (
	"fmt"
	"golang.org/x/sys/windows"
	"time"
)

func waitParent(pid int, timeout time.Duration) error {
	if pid <= 0 {
		return fmt.Errorf("processo pai inválido")
	}
	h, e := windows.OpenProcess(windows.SYNCHRONIZE, false, uint32(pid))
	if e == windows.ERROR_INVALID_PARAMETER {
		return nil
	}
	if e != nil {
		return e
	}
	defer windows.CloseHandle(h)
	status, e := windows.WaitForSingleObject(h, uint32(timeout.Milliseconds()))
	if e != nil {
		return e
	}
	if status != windows.WAIT_OBJECT_0 {
		return fmt.Errorf("aplicativo ainda em execução")
	}
	return nil
}
