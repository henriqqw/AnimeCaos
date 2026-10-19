package integrations

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"sync"
	"time"
)

type Discord struct {
	configMu sync.Mutex
	mu       sync.Mutex
	writeMu  sync.Mutex
	conn     net.Conn
	enabled  bool
	title    string
	episode  float64
	started  int64
	wake     chan struct{}
	cancel   context.CancelFunc
	done     chan struct{}
	dial     func() (net.Conn, error)
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
	d.mu.Lock()
	defer d.mu.Unlock()
	if d.title != title || d.episode != episode {
		d.started = time.Now().Unix()
	}
	d.title = title
	d.episode = episode
	if d.enabled {
		select {
		case d.wake <- struct{}{}:
		default:
		}
	}
	return nil
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
	if err = d.write(c, 0, map[string]any{"v": 1, "client_id": "1494706525426421760"}); err != nil {
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
				activity = map[string]any{"details": d.title, "state": fmt.Sprintf("Ep. %g", d.episode), "timestamps": map[string]int64{"start": d.started}, "assets": map[string]string{"large_image": "logo", "large_text": "AnimeCaos"}}
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
