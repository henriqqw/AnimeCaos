package player

import (
	"context"
	"os"
	"testing"
	"time"
)

func TestDownloadedEpisodeOffline(t *testing.T) {
	file := os.Getenv("ANIMECAOS_MEDIA_TEST_FILE")
	if file == "" {
		t.Skip("set ANIMECAOS_MEDIA_TEST_FILE to verify decoded offline audio/video, seek and EOF")
	}
	events := make(chan State, 256)
	c := New(func(s State) { events <- s })
	defer c.Stop()
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if e := c.Start(ctx, file, "mpv", "", 0, "offline"); e != nil {
		t.Fatal(e)
	}
	seeked := false
	for {
		select {
		case <-ctx.Done():
			t.Fatal("offline playback timed out")
		case s := <-events:
			if s.Position > 1 && s.Duration > 5 && !seeked {
				if s.VideoCodec == "" || s.AudioCodec == "" {
					continue
				}
				if e := c.Command("seek", s.Duration-2); e != nil {
					t.Fatal(e)
				}
				seeked = true
			}
			if !s.Playing {
				if s.Error != "" {
					t.Fatal(s.Error)
				}
				if !s.EOF || !seeked {
					t.Fatalf("seek/EOF failed: %+v", s)
				}
				t.Logf("decoded video=%s audio=%s duration=%.2fs; seek and natural EOF passed", s.VideoCodec, s.AudioCodec, s.Duration)
				return
			}
		}
	}
}
