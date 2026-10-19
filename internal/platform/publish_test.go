package platform

import (
	"os"
	"path/filepath"
	"testing"
)

func TestPublishNeverOverwrites(t *testing.T) {
	dir := t.TempDir()
	temp := filepath.Join(dir, "part")
	dest := filepath.Join(dir, "final")
	os.WriteFile(temp, []byte("new"), 0600)
	os.WriteFile(dest, []byte("old"), 0600)
	if Publish(temp, dest) == nil {
		t.Fatal("overwrote destination")
	}
	b, _ := os.ReadFile(dest)
	if string(b) != "old" {
		t.Fatal("lost original")
	}
	os.Remove(dest)
	if e := Publish(temp, dest); e != nil {
		t.Fatal(e)
	}
	if _, e := os.Stat(temp); !os.IsNotExist(e) {
		t.Fatal("temporary file retained")
	}
}
