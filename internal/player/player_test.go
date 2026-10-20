package player

import (
	"context"
	"fmt"
	"io"
	"math"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	"github.com/henriqqw/animecaos/internal/platform"
)

func TestMPVIntegration(t *testing.T) {
	if os.Getenv("ANIMECAOS_PLAYER_TEST") != "1" {
		t.Skip("set ANIMECAOS_PLAYER_TEST=1 to launch MPV with generated audiovisual media")
	}
	ffmpeg, e := platform.Binary("ffmpeg")
	if e != nil {
		t.Fatal(e)
	}
	fixture := filepath.Join(t.TempDir(), "audio-video.mp4")
	cmd := exec.Command(ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "3", "-c:v", "libx264", "-c:a", "aac", "-y", fixture)
	platform.Hide(cmd)
	if b, e := cmd.CombinedOutput(); e != nil {
		t.Fatalf("fixture: %s %v", b, e)
	}
	for _, manual := range []bool{false, true} {
		t.Run(fmt.Sprint("manual-", manual), func(t *testing.T) {
			events := make(chan State, 256)
			c := New(func(s State) { events <- s })
			defer c.Stop()
			ctx, cancel := context.WithTimeout(context.Background(), 25*time.Second)
			defer cancel()
			if e := c.start(ctx, fixture, "mpv", "", 0, "test", []string{"--vo=null", "--ao=null", "--speed=0.25"}); e != nil {
				t.Fatal(e)
			}
			stopped := false
			var position float64
			seeked := false
			seekTarget := 1.5
			for {
				select {
				case <-ctx.Done():
					t.Fatal("player timeout")
				case s := <-events:
					position = max(position, s.Position)
					if !manual && s.Position > .5 && !seeked {
						if e := c.Command("seek", seekTarget); e != nil {
							t.Fatal(e)
						}
						seeked = true
					}
					if manual && s.Position > .5 && !stopped {
						stopped = true
						c.Stop()
					}
					if !s.Playing {
						if s.Error != "" {
							t.Fatal(s.Error)
						}
						if s.EOF == manual {
							t.Fatalf("incorrect EOF: %+v", s)
						}
						if position <= 0 {
							t.Fatal("no media playback progress")
						}
						if !manual && (!seeked || position <= seekTarget) {
							t.Fatalf("seek did not advance playback: seeked=%t position=%.2f", seeked, position)
						}
						t.Logf("EOF=%v duration=%.2f observedPosition=%.2f codecs=%s/%s dimensions=%dx%d", s.EOF, s.Duration, position, s.VideoCodec, s.AudioCodec, s.Width, s.Height)
						return
					}
				}
			}
		})
	}
}

func TestIPCSignalsNaturalEOFOnly(t *testing.T) {
	for _, reason := range []string{"eof", "quit", "error", "stop"} {
		t.Run(reason, func(t *testing.T) {
			c := New(func(State) {})
			c.state = State{Session: "a", Playing: true}
			local, remote := net.Pipe()
			done := make(chan struct{})
			go func() { c.read(local, "a", time.Now()); close(done) }()
			io.WriteString(remote, `{"event":"property-change","name":"time-pos","data":42}`+"\n"+`{"event":"property-change","name":"video-params/w","data":1920}`+"\n"+`{"event":"property-change","name":"video-params/h","data":1080}`+"\n"+`{"event":"end-file","reason":"`+reason+`"}`+"\n")
			remote.Close()
			<-done
			if c.State().EOF != (reason == "eof") {
				t.Fatalf("reason %s state %+v", reason, c.State())
			}
			if c.State().Position != 42 {
				t.Fatal("position lost")
			}
			if c.State().Width != 1920 || c.State().Height != 1080 {
				t.Fatalf("video dimensions lost: %+v", c.State())
			}
		})
	}
}

func TestEpisodeWatchedRequiresEOFOrEightyPercent(t *testing.T) {
	tests := []struct {
		name     string
		eof      bool
		position float64
		duration float64
		want     bool
	}{
		{name: "natural EOF", eof: true, position: 12, duration: 300, want: true},
		{name: "eighty percent", position: 240, duration: 300, want: true},
		{name: "almost eighty percent", position: 239.9, duration: 300},
		{name: "closed early", position: 31, duration: 1400},
		{name: "unknown duration", position: 1400},
		{name: "invalid position", position: math.NaN(), duration: 1400},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := episodeWatched(tt.eof, tt.position, tt.duration); got != tt.want {
				t.Fatalf("episodeWatched(%v, %v, %v) = %v, want %v", tt.eof, tt.position, tt.duration, got, tt.want)
			}
		})
	}
}

func TestOldPlayerSessionIgnored(t *testing.T) {
	c := New(func(State) {})
	c.state = State{Session: "new"}
	a, b := net.Pipe()
	done := make(chan struct{})
	go func() { c.read(a, "old", time.Now()); close(done) }()
	io.WriteString(b, `{"event":"end-file","reason":"eof"}`+"\n")
	b.Close()
	<-done
	if c.State().EOF {
		t.Fatal("old event modified new player")
	}
}
