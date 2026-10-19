package player

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"math"
	"net"
	"os/exec"
	"sync"
	"time"

	"github.com/henriqqw/animecaos/internal/media"
	"github.com/henriqqw/animecaos/internal/platform"
)

const watchedEpisodeRatio = 0.8

func episodeWatched(eof bool, position, duration float64) bool {
	if eof {
		return true
	}
	if duration <= 0 || position < 0 || math.IsNaN(position) || math.IsInf(position, 0) || math.IsNaN(duration) || math.IsInf(duration, 0) {
		return false
	}
	return position >= duration*watchedEpisodeRatio
}

type State struct {
	Playing    bool    `json:"playing"`
	Paused     bool    `json:"paused"`
	Position   float64 `json:"position"`
	Duration   float64 `json:"duration"`
	EOF        bool    `json:"eof"`
	Watched    bool    `json:"watched"`
	Error      string  `json:"error"`
	Session    string  `json:"session"`
	VideoCodec string  `json:"videoCodec"`
	AudioCodec string  `json:"audioCodec"`
	Width      int     `json:"width"`
	Height     int     `json:"height"`
}
type Controller struct {
	startMu sync.Mutex
	wg      sync.WaitGroup
	mu      sync.Mutex
	writeMu sync.Mutex
	conn    net.Conn
	cancel  context.CancelFunc
	state   State
	emit    func(State)
}

func New(emit func(State)) *Controller { return &Controller{emit: emit} }
func (c *Controller) State() State     { c.mu.Lock(); defer c.mu.Unlock(); return c.state }
func (c *Controller) Close()           { c.startMu.Lock(); defer c.startMu.Unlock(); c.Stop(); c.wg.Wait() }
func (c *Controller) send(args ...any) error {
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	c.mu.Lock()
	conn := c.conn
	c.mu.Unlock()
	if conn == nil {
		return fmt.Errorf("player ainda não conectado")
	}
	conn.SetWriteDeadline(time.Now().Add(2 * time.Second))
	return json.NewEncoder(conn).Encode(map[string]any{"command": args})
}
func (c *Controller) Command(name string, value float64) error {
	switch name {
	case "pause":
		return c.send("cycle", "pause")
	case "seek":
		return c.send("seek", value, "absolute")
	case "volume":
		return c.send("set_property", "volume", value)
	case "stop":
		c.Stop()
		return nil
	}
	return fmt.Errorf("comando de player inválido")
}
func (c *Controller) Stop() {
	c.mu.Lock()
	cancel := c.cancel
	conn := c.conn
	c.cancel = nil
	c.conn = nil
	c.state.EOF = false
	c.mu.Unlock()
	if cancel != nil {
		cancel()
	}
	if conn != nil {
		conn.Close()
	}
}
func (c *Controller) Start(parent context.Context, url, mode, path string, start float64, session string) error {
	c.startMu.Lock()
	defer c.startMu.Unlock()
	c.Stop()
	if mode == "system" {
		return platform.Open(url)
	}
	if mode == "mpv" {
		var e error
		path, e = platform.Binary("mpv")
		if e != nil {
			return e
		}
	}
	if path == "" {
		return fmt.Errorf("selecione o executável do player")
	}
	ctx, cancel := context.WithCancel(parent)
	ipc := ipcPath(media.ID())
	args := []string{url}
	if mode == "mpv" {
		args = append(args, "--no-config", "--ytdl=no", "--idle=no", "--force-window=yes", "--ontop", "--autofit=70%", "--hls-bitrate=max", "--input-ipc-server="+ipc, "--start="+fmt.Sprint(start), "--msg-level=all=warn", "--demuxer-lavf-o=allowed_extensions=ALL")
	}
	cmd := exec.CommandContext(ctx, path, args...)
	platform.Hide(cmd)
	if e := cmd.Start(); e != nil {
		cancel()
		return e
	}
	c.mu.Lock()
	c.cancel = cancel
	c.state = State{Playing: true, Session: session}
	c.mu.Unlock()
	c.emit(c.State())
	c.wg.Add(1)
	go func() {
		defer c.wg.Done()
		defer cancel()
		defer cleanIPC(ipc)
		started := time.Now()
		done := make(chan error, 1)
		readDone := make(chan struct{})
		reading := false
		go func() { done <- cmd.Wait() }()
		if mode == "mpv" {
			var conn net.Conn
			for i := 0; i < 100; i++ {
				if ctx.Err() != nil {
					break
				}
				dialctx, dc := context.WithTimeout(ctx, 100*time.Millisecond)
				x, e := dialIPC(dialctx, ipc)
				dc()
				if e == nil {
					conn = x
					break
				}
				select {
				case <-ctx.Done():
				case <-time.After(50 * time.Millisecond):
				}
			}
			if conn != nil {
				c.mu.Lock()
				if c.state.Session == session {
					c.conn = conn
				}
				c.mu.Unlock()
				for i, p := range []string{"time-pos", "duration", "pause", "video-codec", "audio-codec-name", "video-params/w", "video-params/h"} {
					c.send("observe_property", i+1, p)
				}
				reading = true
				go func() { defer close(readDone); c.read(conn, session, started) }()
			} else if ctx.Err() == nil {
				cancel()
				c.mu.Lock()
				if c.state.Session == session {
					c.state.Error = "Não foi possível conectar ao MPV por IPC"
				}
				c.mu.Unlock()
			}
		}
		err := <-done
		// Drain end-file from IPC before publishing the terminal state. Wait()
		// can return before the reader observes natural EOF on fast media.
		if reading {
			select {
			case <-readDone:
			case <-time.After(time.Second):
			}
		}
		c.mu.Lock()
		if c.state.Session != session {
			c.mu.Unlock()
			return
		}
		conn := c.conn
		c.conn = nil
		c.cancel = nil
		c.state.Playing = false
		if ctx.Err() != nil {
			c.state.EOF = false
		}
		c.state.Watched = episodeWatched(c.state.EOF, c.state.Position, c.state.Duration)
		if err != nil && ctx.Err() == nil {
			c.state.Error = "Player encerrou com erro: " + err.Error()
		}
		state := c.state
		c.mu.Unlock()
		if conn != nil {
			conn.Close()
		}
		c.emit(state)
	}()
	return nil
}
func (c *Controller) read(conn net.Conn, session string, started time.Time) {
	defer conn.Close()
	scanner := bufio.NewScanner(conn)
	for scanner.Scan() {
		var ev struct {
			Event  string          `json:"event"`
			Name   string          `json:"name"`
			Data   json.RawMessage `json:"data"`
			Reason string          `json:"reason"`
		}
		if json.Unmarshal(scanner.Bytes(), &ev) != nil {
			continue
		}
		c.mu.Lock()
		if c.state.Session != session {
			c.mu.Unlock()
			return
		}
		if ev.Event == "property-change" {
			switch ev.Name {
			case "time-pos":
				json.Unmarshal(ev.Data, &c.state.Position)
			case "duration":
				json.Unmarshal(ev.Data, &c.state.Duration)
			case "pause":
				json.Unmarshal(ev.Data, &c.state.Paused)
			case "video-codec":
				json.Unmarshal(ev.Data, &c.state.VideoCodec)
			case "audio-codec-name":
				json.Unmarshal(ev.Data, &c.state.AudioCodec)
			case "video-params/w":
				json.Unmarshal(ev.Data, &c.state.Width)
			case "video-params/h":
				json.Unmarshal(ev.Data, &c.state.Height)
			}
		}
		if ev.Event == "end-file" {
			c.state.EOF = ev.Reason == "eof"
			if ev.Reason == "error" {
				c.state.Error = "Falha ao reproduzir o vídeo"
			}
		}
		s := c.state
		c.mu.Unlock()
		c.emit(s)
	}
}
