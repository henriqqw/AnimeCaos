package providers

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"path/filepath"
	"strings"
	"testing"
)

func TestFindFirefoxRejectsMissingConfiguredBinary(t *testing.T) {
	t.Setenv("ANIMECAOS_FIREFOX_PATH", filepath.Join(t.TempDir(), "missing-firefox.exe"))
	if path, err := findFirefox(); err == nil || path != "" {
		t.Fatalf("expected configured missing Firefox to fail, got path=%q err=%v", path, err)
	}
}

func TestSeleniumUsesJWPlayerConfigAndSupportsVisibleFirefox(t *testing.T) {
	if !strings.Contains(renderedPlayerInspectScript, "jwplayer") || !strings.Contains(renderedPlayerInspectScript, "getPlaylistItem") || !strings.Contains(renderedPlayerInspectScript, "player.play()") {
		t.Fatal("Selenium player inspection must read and activate JWPlayer when its media URL is not yet exposed")
	}
	if !strings.Contains(renderedPlayerInspectScript, "window.__animecaosPlayTriggered = true") || !strings.Contains(renderedPlayerInspectScript, "video.muted = true") || !strings.Contains(renderedPlayerInspectScript, "video.play()") {
		t.Fatal("Selenium player inspection must activate a scoped HTML5 video silently when its media URL is not yet exposed")
	}
	if !strings.Contains(renderedPlayerInspectScript, "player-container") || !strings.Contains(renderedPlayerInspectScript, "adInterstitial") {
		t.Fatal("Selenium inspection must scope media to the player and detect its ad interstitial")
	}
	t.Setenv("ANIMECAOS_BROWSER_HEADLESS", "0")
	if args := seleniumFirefoxArgs(); len(args) != 0 {
		t.Fatalf("visible Firefox should use an empty args array, got %#v", args)
	}
	t.Setenv("ANIMECAOS_BROWSER_HEADLESS", "1")
	if args := seleniumFirefoxArgs(); len(args) != 1 || args[0] != "-headless" {
		t.Fatalf("headless Firefox args = %#v", args)
	}
	cacheDir := filepath.Join(t.TempDir(), "isolated-cache")
	prefs := seleniumFirefoxPrefs(&url.URL{Host: "127.0.0.1:43210"}, cacheDir)
	for key, expected := range map[string]any{
		"network.proxy.type":                                1,
		"network.proxy.http":                                "127.0.0.1",
		"network.proxy.http_port":                           43210,
		"network.proxy.ssl_port":                            43210,
		"network.proxy.no_proxies_on":                       "",
		"network.proxy.failover_direct":                     false,
		"dom.disable_open_during_load":                      true,
		"privacy.trackingprotection.enabled":                true,
		"privacy.trackingprotection.socialtracking.enabled": true,
		"browser.cache.disk.enable":                         true,
		"browser.cache.disk.parent_directory":               cacheDir,
	} {
		if prefs[key] != expected {
			t.Errorf("Firefox preference %s = %#v, want %#v", key, prefs[key], expected)
		}
	}
	plainBrowserPrefs := seleniumFirefoxPrefs(nil, "")
	if plainBrowserPrefs["network.proxy.type"] != nil || plainBrowserPrefs["privacy.trackingprotection.pbmode.enabled"] != nil {
		t.Fatalf("Firefox preferences without a browser proxy should avoid proxy-specific settings: %#v", plainBrowserPrefs)
	}
	caps := seleniumFirefoxCapabilities("/firefox", nil, cacheDir)
	capabilities := caps["capabilities"].(map[string]any)["alwaysMatch"].(map[string]any)
	if capabilities["pageLoadStrategy"] != "eager" {
		t.Fatalf("Firefox pageLoadStrategy = %#v, want eager", capabilities["pageLoadStrategy"])
	}
	options := capabilities["moz:firefoxOptions"].(map[string]any)
	if options["binary"] != "/firefox" || options["prefs"].(map[string]any)["browser.cache.disk.parent_directory"] != cacheDir {
		t.Fatalf("Firefox options did not receive the binary and isolated cache directory: %#v", options)
	}
}

func TestWebdriverCallReturnsScriptValue(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"value":{"blocked":false,"urls":["https://video.example/episode.m3u8"]}}`))
	}))
	defer server.Close()
	value, err := webdriverCall(context.Background(), server.Client(), http.MethodPost, server.URL, map[string]any{"script": "return true"})
	if err != nil {
		t.Fatal(err)
	}
	if string(value) != `{"blocked":false,"urls":["https://video.example/episode.m3u8"]}` {
		t.Fatalf("unexpected WebDriver value %s", value)
	}
}

func TestWebdriverCallSurfacesW3CError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"value":{"error":"session not created","message":"Firefox is missing"}}`))
	}))
	defer server.Close()
	_, err := webdriverCall(context.Background(), server.Client(), http.MethodPost, server.URL, map[string]any{})
	if err == nil || err.Error() != "WebDriver session not created: Firefox is missing" {
		t.Fatalf("unexpected WebDriver error: %v", err)
	}
}
