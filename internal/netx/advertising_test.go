package netx

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestIsAdvertisingURLMatchesOnlyKnownHostSuffixes(t *testing.T) {
	for _, raw := range []string{
		"https://t.dtscout.com/track",
		"https://tags.crwdcntrl.net/pixel",
		"https://sub.doubleclick.net/ad.js",
	} {
		if !IsAdvertisingURL(raw) {
			t.Errorf("known ad host was not identified: %s", raw)
		}
	}
	for _, raw := range []string{
		"https://video.example/episode.m3u8",
		"https://notdoubleclick.net/video.mp4",
		"https://cdn.example/stream?next=https://doubleclick.net/ad",
	} {
		if IsAdvertisingURL(raw) {
			t.Errorf("legitimate host was identified as advertising: %s", raw)
		}
	}
}

func TestClientDoesNotFollowRedirectToKnownAdvertisingHost(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Location", "https://t.dtscout.com/tracker")
		w.WriteHeader(http.StatusFound)
	}))
	defer server.Close()

	_, err := New().Do(context.Background(), http.MethodGet, server.URL, nil, nil)
	var responseErr *HTTPError
	if !errors.As(err, &responseErr) || responseErr.Status != http.StatusFound {
		t.Fatalf("expected original 302 response to be returned, got %v", err)
	}
}

func TestClientStillFollowsOrdinaryRedirects(t *testing.T) {
	final := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusNoContent) }))
	defer final.Close()
	redirect := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Location", final.URL)
		w.WriteHeader(http.StatusFound)
	}))
	defer redirect.Close()

	response, err := New().Do(context.Background(), http.MethodGet, redirect.URL, nil, nil)
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	if response.StatusCode != http.StatusNoContent {
		t.Fatalf("ordinary redirect status = %d, want 204", response.StatusCode)
	}
}
