package providers

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestFindFirefoxRejectsMissingConfiguredBinary(t *testing.T) {
	t.Setenv("ANIMECAOS_FIREFOX_PATH", filepath.Join(t.TempDir(), "missing-firefox.exe"))
	if path, err := findFirefox(); err == nil || path != "" {
		t.Fatalf("expected configured missing Firefox to fail, got path=%q err=%v", path, err)
	}
}

func TestBundledBrowserPathsMatchWindowsAndAppImageLayouts(t *testing.T) {
	root := t.TempDir()
	windows := bundledFirefoxLocations(root, "windows")
	if len(windows) != 1 || windows[0] != filepath.Join(root, "bin", "firefox", "firefox.exe") {
		t.Fatalf("Windows Firefox path = %#v", windows)
	}
	linuxFirefox := bundledFirefoxLocations(root, "linux")
	if len(linuxFirefox) != 2 || linuxFirefox[0] != filepath.Join(root, "bin", "firefox", "firefox") || linuxFirefox[1] != filepath.Clean(filepath.Join(root, "..", "lib", "firefox", "firefox")) {
		t.Fatalf("Linux Firefox paths = %#v", linuxFirefox)
	}
	if got := bundledGeckodriverLocations(root, "windows"); len(got) != 2 || got[0] != filepath.Join(root, "bin", "geckodriver.exe") {
		t.Fatalf("Windows GeckoDriver paths = %#v", got)
	}
	if got := bundledGeckodriverLocations(root, "linux"); len(got) != 2 || got[1] != filepath.Join(root, "geckodriver") {
		t.Fatalf("Linux AppImage GeckoDriver paths = %#v", got)
	}
}

func TestBundledFirefoxDynamicPlayerFixture(t *testing.T) {
	if os.Getenv("ANIMECAOS_BROWSER_TEST") != "1" {
		t.Skip("set ANIMECAOS_BROWSER_TEST=1 to exercise the bundled Firefox runtime")
	}
	driverPath := strings.TrimSpace(os.Getenv("ANIMECAOS_GECKODRIVER_PATH"))
	if driverPath == "" {
		var err error
		driverPath, err = findBundledGeckodriver(runtimeExecutableDir())
		if err != nil {
			t.Fatal(err)
		}
	}
	if _, err := findFirefox(); err != nil {
		t.Fatal(err)
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		if r.URL.Path == "/" {
			_, _ = w.Write([]byte(`<!doctype html><html><body><div class="player-container"></div><script>
setTimeout(() => { const frame = document.createElement('iframe'); frame.src = '/embed/episode-1'; document.querySelector('.player-container').appendChild(frame); }, 150);
</script></body></html>`))
			return
		}
		_, _ = w.Write([]byte(`<html><body>fixture player</body></html>`))
	}))
	defer server.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 18*time.Second)
	defer cancel()
	urls, err := seleniumPlayerURLs(ctx, server.URL, driverPath, nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(urls) != 1 || urls[0].URL != server.URL+"/embed/episode-1" {
		t.Fatalf("bundled Firefox did not return dynamically created player iframe: %#v", urls)
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
