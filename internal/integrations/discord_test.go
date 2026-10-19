package integrations

import (
	"encoding/json"
	"net"
	"sync/atomic"
	"testing"
	"time"
)

func TestDiscordActivityPingClearAndReconnect(t *testing.T) {
	type event struct {
		op   uint32
		data []byte
	}
	events := make(chan event, 32)
	var connections atomic.Int32
	d := &Discord{}
	d.dial = func() (net.Conn, error) {
		client, server := net.Pipe()
		connections.Add(1)
		go func() {
			defer server.Close()
			if op, _, err := discordFrame(server); err != nil || op != 0 {
				return
			}
			writer := &Discord{}
			if writer.write(server, 1, map[string]any{"evt": "READY"}) != nil {
				return
			}
			pinged := false
			for {
				op, b, err := discordFrame(server)
				if err != nil {
					return
				}
				events <- event{op, b}
				if !pinged {
					pinged = true
					if writer.write(server, 3, map[string]int{"ping": 42}) != nil {
						return
					}
				}
			}
		}()
		return client, nil
	}
	d.Update("Anime", 3)
	d.Configure(true)
	defer d.Close()
	wait := func(predicate func(event) bool) {
		t.Helper()
		deadline := time.NewTimer(3 * time.Second)
		defer deadline.Stop()
		for {
			select {
			case ev := <-events:
				if predicate(ev) {
					return
				}
			case <-deadline.C:
				t.Fatal("missing Discord event")
			}
		}
	}
	wait(func(e event) bool { return e.op == 4 && string(e.data) == `{"ping":42}` })
	if !d.Connected() {
		t.Fatal("not connected")
	}
	d.Update("", 0)
	wait(func(e event) bool {
		var payload struct {
			Args struct {
				Activity json.RawMessage `json:"activity"`
			} `json:"args"`
		}
		return e.op == 1 && json.Unmarshal(e.data, &payload) == nil && string(payload.Args.Activity) == "null"
	})
	d.mu.Lock()
	c := d.conn
	d.mu.Unlock()
	d.drop(c)
	d.Update("Another", 4)
	wait(func(e event) bool { return e.op == 4 })
	if connections.Load() != 2 {
		t.Fatal("did not reconnect")
	}
	d.Configure(false)
	if d.Connected() {
		t.Fatal("connection remained after disable")
	}
}
