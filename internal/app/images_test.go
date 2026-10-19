package app

import (
	"bytes"
	"context"
	"crypto/md5"
	"encoding/hex"
	"image"
	"image/png"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
)

func TestLegacyImageIsAvailableOffline(t *testing.T) {
	s, err := New(context.Background(), t.TempDir(), nil)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	u := "http://127.0.0.1:1/unreachable-cover.jpg"
	hash := md5.Sum([]byte(u))
	dir := filepath.Join(s.db.Dir, "cache", "covers")
	os.MkdirAll(dir, 0700)
	var data bytes.Buffer
	png.Encode(&data, image.NewRGBA(image.Rect(0, 0, 2, 2)))
	os.WriteFile(filepath.Join(dir, hex.EncodeToString(hash[:])+".jpg"), data.Bytes(), 0600)
	value, err := s.Image(u)
	if err != nil || !strings.HasPrefix(value, "data:image/png;base64,") {
		t.Fatalf("legacy cover unavailable: %v", err)
	}
}
func TestImageFailuresAreCached(t *testing.T) {
	s, err := New(context.Background(), t.TempDir(), nil)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	var requests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { requests.Add(1); http.NotFound(w, r) }))
	defer server.Close()
	for range 3 {
		if _, err = s.Image(server.URL + "/gone.jpg"); err == nil {
			t.Fatal("missing image succeeded")
		}
	}
	if requests.Load() != 1 {
		t.Fatalf("failed cover requested %d times", requests.Load())
	}
}
