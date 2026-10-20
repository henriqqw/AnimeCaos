package integrations

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net"
	"os"
	"strings"
	"sync"
	"time"
)

type Discord struct {
	configMu       sync.Mutex
	mu             sync.Mutex
	writeMu        sync.Mutex
	conn           net.Conn
	enabled        bool
	title          string
	season         int
	episode        float64
	epTitle        string
	started        int64
	paused         bool
	lastPosition   float64
	lastPositionAt time.Time
	wake           chan struct{}
	cancel         context.CancelFunc
	done           chan struct{}
	dial           func() (net.Conn, error)
}

func (d *Discord) Configure(enabled bool) {
	d.configMu.Lock()
	defer d.configMu.Unlock()
	d.mu.Lock()
	if d.enabled == enabled {
		d.mu.Unlock()
		return
	}
	d.enabled = enabled
	if !enabled {
		d.cancel()
		if d.conn != nil {
			d.conn.Close()
			d.conn = nil
		}
		done := d.done
		d.mu.Unlock()
		<-done
		return
	}
	ctx, cancel := context.WithCancel(context.Background())
	d.cancel = cancel
	d.wake = make(chan struct{}, 1)
	d.done = make(chan struct{})
	wake, done := d.wake, d.done
	d.mu.Unlock()
	go d.loop(ctx, wake, done)
}
func (d *Discord) Close()          { d.Configure(false) }
func (d *Discord) Connected() bool { d.mu.Lock(); defer d.mu.Unlock(); return d.conn != nil }

// Update changes desired state; network activity runs independently of playback.
func (d *Discord) Update(title string, episode float64) error {
	d.UpdatePlayback(DiscordPlayback{Title: title, Episode: episode, Playing: title != ""})
	return nil
}

type DiscordPlayback struct {
	Title        string
	Season       int
	Episode      float64
	EpisodeTitle string
	Position     float64
	Playing      bool
	Paused       bool
}

// UpdatePlayback maps the current MPV position to Discord's elapsed-time
// timestamp. It sends IPC updates only when the item, pause state, or seek
// changes; ordinary position ticks let Discord advance the clock itself.
func (d *Discord) UpdatePlayback(playback DiscordPlayback) {
	d.mu.Lock()
	defer d.mu.Unlock()
	active := strings.TrimSpace(playback.Title) != "" && (playback.Playing || playback.Paused)
	changed := false
	if !active {
		changed = d.title != ""
		d.title = ""
		d.season = 0
		d.episode = 0
		d.epTitle = ""
		d.started = 0
		d.paused = false
		d.lastPositionAt = time.Time{}
	} else {
		now := time.Now()
		position := math.Max(0, playback.Position)
		sameItem := d.title == playback.Title && d.season == playback.Season && d.episode == playback.Episode && d.epTitle == playback.EpisodeTitle
		if !sameItem {
			d.started = now.Unix() - int64(position)
			changed = true
		} else if playback.Paused != d.paused {
			if playback.Paused {
				d.started = 0
			} else {
				d.started = now.Unix() - int64(position)
			}
			changed = true
		} else if playback.Playing && !playback.Paused && !d.lastPositionAt.IsZero() {
			expected := d.lastPosition + now.Sub(d.lastPositionAt).Seconds()
			if math.Abs(position-expected) > 6 {
				d.started = now.Unix() - int64(position)
				changed = true
			}
		}
		d.title = playback.Title
		d.season = playback.Season
		d.episode = playback.Episode
		d.epTitle = playback.EpisodeTitle
		d.paused = playback.Paused
		d.lastPosition = position
		d.lastPositionAt = now
	}
	if changed && d.enabled {
		select {
		case d.wake <- struct{}{}:
		default:
		}
	}
}
func discordFrame(c net.Conn) (uint32, []byte, error) {
	var header [8]byte
	if _, err := io.ReadFull(c, header[:]); err != nil {
		return 0, nil, err
	}
	n := binary.LittleEndian.Uint32(header[4:])
	if n > 1<<20 {
		return 0, nil, fmt.Errorf("resposta Discord inválida")
	}
	b := make([]byte, n)
	_, err := io.ReadFull(c, b)
	return binary.LittleEndian.Uint32(header[:4]), b, err
}
func (d *Discord) write(c net.Conn, op uint32, data any) error {
	b, err := json.Marshal(data)
	if err != nil {
		return err
	}
	var header [8]byte
	binary.LittleEndian.PutUint32(header[:4], op)
	binary.LittleEndian.PutUint32(header[4:], uint32(len(b)))
	d.writeMu.Lock()
	defer d.writeMu.Unlock()
	c.SetWriteDeadline(time.Now().Add(time.Second))
	_, err = io.Copy(c, bytes.NewReader(append(header[:], b...)))
	return err
}
func (d *Discord) drop(c net.Conn) {
	d.mu.Lock()
	if d.conn == c {
		d.conn = nil
	}
	d.mu.Unlock()
	c.Close()
}
func (d *Discord) connect(ctx context.Context) (net.Conn, error) {
	d.mu.Lock()
	c := d.conn
	dial := d.dial
	d.mu.Unlock()
	if c != nil {
		return c, nil
	}
	if dial == nil {
		dial = dialDiscord
	}
	c, err := dial()
	if err != nil {
		return nil, err
	}
	fail := func(e error) (net.Conn, error) { c.Close(); return nil, e }
	if ctx.Err() != nil {
		return fail(ctx.Err())
	}
	if err = d.write(c, 0, map[string]any{"v": 1, "client_id": DiscordClientID}); err != nil {
		return fail(err)
	}
	c.SetReadDeadline(time.Now().Add(2 * time.Second))
	op, b, err := discordFrame(c)
	if err != nil {
		return fail(err)
	}
	var reply struct {
		Event string `json:"evt"`
	}
	if json.Unmarshal(b, &reply) != nil || op != 1 || reply.Event != "READY" {
		return fail(fmt.Errorf("Discord recusou a conexão"))
	}
	c.SetReadDeadline(time.Time{})
	d.mu.Lock()
	if !d.enabled || ctx.Err() != nil {
		d.mu.Unlock()
		return fail(context.Canceled)
	}
	d.conn = c
	d.mu.Unlock()
	go d.read(c)
	return c, nil
}
func (d *Discord) read(c net.Conn) {
	defer d.drop(c)
	for {
		op, b, err := discordFrame(c)
		if err != nil || op == 2 {
			return
		}
		if op == 3 {
			if err = d.write(c, 4, json.RawMessage(b)); err != nil {
				return
			}
		}
	}
}
func (d *Discord) loop(ctx context.Context, wake <-chan struct{}, done chan<- struct{}) {
	defer close(done)
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()
	for {
		if ctx.Err() != nil {
			return
		}
		c, err := d.connect(ctx)
		if err == nil {
			d.mu.Lock()
			var activity any
			if d.title != "" {
				state := discordEpisodeState(d.season, d.episode, d.epTitle, d.paused)
				activity = map[string]any{"details": truncateDiscordText(d.title), "state": state, "assets": map[string]string{"large_image": "logo", "large_text": "AnimeCaos"}}
				if !d.paused && d.started > 0 {
					activity.(map[string]any)["timestamps"] = map[string]int64{"start": d.started}
				}
			}
			d.mu.Unlock()
			if d.write(c, 1, map[string]any{"cmd": "SET_ACTIVITY", "args": map[string]any{"pid": os.Getpid(), "activity": activity}, "nonce": random()}) != nil {
				d.drop(c)
			}
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		case <-wake:
		}
	}
}

func discordEpisodeState(season int, episode float64, title string, paused bool) string {
	var parts []string
	if paused {
		parts = append(parts, "Pausado")
	}
	if season > 0 {
		parts = append(parts, fmt.Sprintf("T%d", season))
	}
	if episode > 0 {
		parts = append(parts, fmt.Sprintf("Ep. %g", episode))
	}
	if title = strings.TrimSpace(title); title != "" {
		parts = append(parts, title)
	}
	if len(parts) == 0 {
		return "Assistindo"
	}
	return truncateDiscordText(strings.Join(parts, " · "))
}

func truncateDiscordText(value string) string {
	runes := []rune(strings.TrimSpace(value))
	if len(runes) <= 128 {
		return string(runes)
	}
	return string(runes[:125]) + "…"
}
