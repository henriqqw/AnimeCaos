//go:build !windows

package integrations

import (
	"fmt"
	"net"
	"os"
	"path/filepath"
	"time"
)

func dialDiscord() (net.Conn, error) {
	for _, root := range []string{os.Getenv("XDG_RUNTIME_DIR"), os.Getenv("TMPDIR"), "/tmp"} {
		if root == "" {
			continue
		}
		for _, sub := range []string{"", "app/com.discordapp.Discord", "snap.discord"} {
			for i := 0; i < 10; i++ {
				c, e := net.DialTimeout("unix", filepath.Join(root, sub, fmt.Sprintf("discord-ipc-%d", i)), 100*time.Millisecond)
				if e == nil {
					return c, nil
				}
			}
		}
	}
	return nil, fmt.Errorf("Discord não está aberto")
}
