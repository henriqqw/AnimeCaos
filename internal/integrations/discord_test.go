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

func TestDiscordPresenceShowsAnimeEpisodePauseAndElapsedTime(t *testing.T) {
	activities := make(chan []byte, 8)
	d := &Discord{}
	d.dial = func() (net.Conn, error) {
		client, server := net.Pipe()
		go func() {
			defer server.Close()
			if op, _, err := discordFrame(server); err != nil || op != 0 {
				return
			}
			writer := &Discord{}
			if writer.write(server, 1, map[string]any{"evt": "READY"}) != nil {
				return
			}
			for {
				op, payload, err := discordFrame(server)
				if err != nil {
					return
				}
				if op == 1 {
					activities <- payload
				}
			}
		}()
		return client, nil
	}
	d.UpdatePlayback(DiscordPlayback{Title: "Hunter x Hunter", Season: 2, Episode: 4, EpisodeTitle: "Esperança", Position: 75, Playing: true})
	d.Configure(true)
	defer d.Close()

	read := func() map[string]any {
		t.Helper()
		select {
		case raw := <-activities:
			var payload map[string]any
			if err := json.Unmarshal(raw, &payload); err != nil {
				t.Fatal(err)
			}
			return payload
		case <-time.After(3 * time.Second):
			t.Fatal("Discord activity update was not sent")
			return nil
		}
	}
	activity := func(payload map[string]any) map[string]any {
		t.Helper()
		args, _ := payload["args"].(map[string]any)
		activity, _ := args["activity"].(map[string]any)
		if activity == nil {
			t.Fatalf("missing activity in payload: %+v", payload)
		}
		return activity
	}
	first := activity(read())
	if first["details"] != "Hunter x Hunter" || first["state"] != "T2 · Ep. 4 · Esperança" || first["assets"].(map[string]any)["large_text"] != "AnimeCaos" {
		t.Fatalf("unexpected Discord activity: %+v", first)
	}
	timestamps, ok := first["timestamps"].(map[string]any)
	if !ok || timestamps["start"] == nil {
		t.Fatalf("elapsed-time timestamp missing from activity: %+v", first)
	}
	if got := int64(timestamps["start"].(float64)); got > time.Now().Unix()-70 || got < time.Now().Unix()-80 {
		t.Fatalf("timestamp does not reflect the MPV position: start=%d", got)
	}

	d.UpdatePlayback(DiscordPlayback{Title: "Hunter x Hunter", Season: 2, Episode: 4, EpisodeTitle: "Esperança", Position: 80, Playing: true, Paused: true})
	paused := activity(read())
	if paused["state"] != "Pausado · T2 · Ep. 4 · Esperança" || paused["timestamps"] != nil {
		t.Fatalf("paused Discord activity should freeze the timer: %+v", paused)
	}

	d.UpdatePlayback(DiscordPlayback{Title: "Hunter x Hunter", Season: 2, Episode: 4, EpisodeTitle: "Esperança", Position: 82, Playing: true})
	resumed := activity(read())
	if resumed["state"] != "T2 · Ep. 4 · Esperança" || resumed["timestamps"] == nil {
		t.Fatalf("resumed Discord activity did not restart its timer: %+v", resumed)
	}
}
