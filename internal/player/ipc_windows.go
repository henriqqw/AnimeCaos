//go:build windows

package player

import (
	"context"
	"github.com/Microsoft/go-winio"
	"net"
)

func ipcPath(id string) string { return `\\.\pipe\animecaos-` + id }
func dialIPC(ctx context.Context, path string) (net.Conn, error) {
	return winio.DialPipeContext(ctx, path)
}
func cleanIPC(path string) {}
