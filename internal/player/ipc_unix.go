//go:build !windows

package player

import (
	"context"
	"net"
	"os"
	"path/filepath"
)

func ipcPath(id string) string { return filepath.Join(os.TempDir(), "animecaos-"+id+".sock") }
func dialIPC(ctx context.Context, path string) (net.Conn, error) {
	return (&net.Dialer{}).DialContext(ctx, "unix", path)
}
func cleanIPC(path string) { os.Remove(path) }
