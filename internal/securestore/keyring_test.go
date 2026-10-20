package securestore

import (
	"fmt"
	"os"
	"testing"
	"time"
)

func TestSystemKeyringRoundTrip(t *testing.T) {
	if os.Getenv("ANIMECAOS_SYSTEM_KEYRING_TEST") != "1" {
		t.Skip("set ANIMECAOS_SYSTEM_KEYRING_TEST=1 to exercise the operating-system credential store")
	}

	store := System{}
	key := fmt.Sprintf("release-smoke-%d", time.Now().UnixNano())
	value := fmt.Sprintf("temporary-credential-%d", time.Now().UnixNano())
	t.Cleanup(func() { _ = store.Delete(key) })

	if err := store.Set(key, value); err != nil {
		t.Fatalf("store operating-system credential: %v", err)
	}
	got, err := store.Get(key)
	if err != nil {
		t.Fatalf("read operating-system credential: %v", err)
	}
	if got != value {
		t.Fatalf("credential round trip mismatch: got %q", got)
	}
	if err := store.Delete(key); err != nil {
		t.Fatalf("delete operating-system credential: %v", err)
	}
	if _, err := store.Get(key); !IsNotFound(err) {
		t.Fatalf("deleted credential should be absent, got %v", err)
	}
}
