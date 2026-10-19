//go:build windows

package integrations

import (
	"context"
	"fmt"
	"github.com/Microsoft/go-winio"
	"net"
	"time"
)

func dialDiscord() (net.Conn, error) {
	for i := 0; i < 10; i++ {
		ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
		c, e := winio.DialPipeContext(ctx, fmt.Sprintf(`\\.\pipe\discord-ipc-%d`, i))
		cancel()
		if e == nil {
			return c, nil
		}
	}
	return nil, fmt.Errorf("Discord não está aberto")
}
