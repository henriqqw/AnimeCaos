package providers

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/henriqqw/animecaos/internal/platform"
)

// Leave headroom inside renderedPlayerTimeout for Firefox startup, navigation,
// and WebDriver cleanup. The browser context remains the hard upper bound.
const seleniumWait = 10 * time.Second
const maxWebdriverResponseSize = 16 << 20
const webDriverTreeKillTimeout = 2 * time.Second

type webdriverValue struct {
	SessionID string          `json:"sessionId"`
	Error     string          `json:"error"`
	Message   string          `json:"message"`
	Value     json.RawMessage `json:"value"`
}

type seleniumSession struct {
	ctx       context.Context
	cancel    context.CancelFunc
	client    *http.Client
	base      string
	sessionID string
	process   *exec.Cmd
	done      chan struct{}
	cacheDir  string
}

func startSeleniumSession(parent context.Context, pageURL, driverPath string, proxy *url.URL) (*seleniumSession, error) {
	firefoxPath, err := findFirefox()
	if err != nil {
		return nil, err
	}
	ctx, cancel := context.WithTimeout(parent, renderedPlayerTimeout)
	session := &seleniumSession{ctx: ctx, cancel: cancel, client: &http.Client{}}
	started := false
	defer func() {
		if !started {
			session.close()
		}
	}()
	cacheDir, err := os.MkdirTemp("", "animecaos-browser-cache-")
	if err != nil {
		return nil, fmt.Errorf("não foi possível criar cache isolado do Firefox: %w", err)
	}
	session.cacheDir = cacheDir
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, err
	}
	port := listener.Addr().(*net.TCPAddr).Port
	_ = listener.Close()
	cmd := exec.CommandContext(ctx, driverPath, "--host", "127.0.0.1", "--port", strconv.Itoa(port))
	platform.HideConsole(cmd)
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("não foi possível iniciar o GeckoDriver: %w", err)
	}
	session.process = cmd
	session.done = make(chan struct{})
	go func() { _ = cmd.Wait(); close(session.done) }()

	base := fmt.Sprintf("http://127.0.0.1:%d", port)
	session.base = base
	// Firefox startup can take longer than an ordinary WebDriver command. The
	// request context already bounds the whole browser operation to 12 s.
	if err := waitWebDriver(ctx, session.client, base); err != nil {
		return nil, fmt.Errorf("GeckoDriver não iniciou: %w", err)
	}
	caps := seleniumFirefoxCapabilities(firefoxPath, proxy, cacheDir)
	created, err := webdriverCall(ctx, session.client, http.MethodPost, base+"/session", caps)
	if err != nil {
		return nil, fmt.Errorf("não foi possível iniciar a sessão Selenium: %w", err)
	}
	var sessionResponse struct {
		SessionID string `json:"sessionId"`
		Value     struct {
			SessionID string `json:"sessionId"`
		} `json:"value"`
	}
	if err := json.Unmarshal(created, &sessionResponse); err != nil {
		return nil, err
	}
	sessionID := sessionResponse.Value.SessionID
	if sessionID == "" {
		sessionID = sessionResponse.SessionID
	}
	if sessionID == "" {
		return nil, fmt.Errorf("GeckoDriver não retornou o identificador da sessão")
	}
	session.sessionID = sessionID
	if _, err := webdriverCall(ctx, session.client, http.MethodPost, base+"/session/"+sessionID+"/url", map[string]string{"url": pageURL}); err != nil {
		return nil, fmt.Errorf("navegação Selenium do player: %w", err)
	}
	started = true
	return session, nil
}

func (s *seleniumSession) execute(script string) (json.RawMessage, error) {
	return webdriverCall(s.ctx, s.client, http.MethodPost, s.base+"/session/"+s.sessionID+"/execute/sync", map[string]any{"script": script, "args": []any{}})
}

func (s *seleniumSession) close() {
	if s.sessionID != "" {
		cleanupCtx, cleanupCancel := context.WithTimeout(context.Background(), 2*time.Second)
		_, _ = webdriverCall(cleanupCtx, s.client, http.MethodDelete, s.base+"/session/"+s.sessionID, nil)
		cleanupCancel()
	}
	// CommandContext terminates GeckoDriver when cancelled, but on Windows that
	// can orphan Firefox. Stop this dedicated process tree first.
	if s.process != nil && s.process.Process != nil {
		if err := stopWebDriverProcessTree(s.process.Process.Pid); err != nil {
			_ = s.process.Process.Kill()
		}
	}
	if s.cancel != nil {
		s.cancel()
	}
	if s.done != nil {
		select {
		case <-s.done:
		case <-time.After(time.Second):
			if s.process != nil && s.process.Process != nil {
				_ = s.process.Process.Kill()
			}
			select {
			case <-s.done:
			case <-time.After(time.Second):
			}
		}
	}
	if s.cacheDir != "" {
		_ = os.RemoveAll(s.cacheDir)
	}
}

// seleniumPlayerURLs is the bounded Firefox/WebDriver path for players that
// add iframes or media only after JavaScript runs. It never interacts with
// security challenges or advertising links.
func seleniumPlayerURLs(parent context.Context, pageURL, driverPath string, proxy *url.URL) ([]playerURLCandidate, error) {
	session, err := startSeleniumSession(parent, pageURL, driverPath, proxy)
	if err != nil {
		return nil, err
	}
	defer session.close()
	deadline := time.NewTimer(seleniumWait)
	defer deadline.Stop()
	ticker := time.NewTicker(250 * time.Millisecond)
	defer ticker.Stop()
	for {
		result, err := session.execute("return " + renderedPlayerInspectScript + ";")
		if err == nil {
			var state renderedPlayerState
			if json.Unmarshal(result, &state) == nil {
				if state.Blocked {
					return nil, fmt.Errorf("página do player permaneceu em verificação de segurança")
				}
				if state.AdInterstitial {
					return nil, fmt.Errorf("player protegido por intersticial de anúncio; nenhum link publicitário foi aberto")
				}
				if len(state.URLs) > 0 {
					return uniquePlayerCandidates(state.URLs), nil
				}
			}
		}
		select {
		case <-session.ctx.Done():
			return nil, session.ctx.Err()
		case <-deadline.C:
			return nil, fmt.Errorf("player Selenium não criou iframe ou vídeo")
		case <-ticker.C:
		}
	}
}

func seleniumFirefoxCapabilities(firefoxPath string, proxy *url.URL, cacheDir string) map[string]any {
	return map[string]any{"capabilities": map[string]any{"alwaysMatch": map[string]any{
		"browserName":      "firefox",
		"pageLoadStrategy": "eager",
		"moz:firefoxOptions": map[string]any{
			"binary": firefoxPath,
			"args":   seleniumFirefoxArgs(),
			"prefs":  seleniumFirefoxPrefs(proxy, cacheDir),
		},
	}}}
}

func seleniumFirefoxPrefs(proxy *url.URL, cacheDir string) map[string]any {
	prefs := map[string]any{
		"dom.disable_open_during_load":            true,
		"dom.popup_maximum":                       0,
		"browser.link.open_newwindow":             3,
		"browser.link.open_newwindow.restriction": 0,
	}
	if cacheDir != "" {
		prefs["browser.cache.disk.enable"] = true
		prefs["browser.cache.disk.parent_directory"] = filepath.Clean(cacheDir)
	}
	if proxy != nil {
		prefs["privacy.trackingprotection.enabled"] = true
		prefs["privacy.trackingprotection.pbmode.enabled"] = true
		prefs["privacy.trackingprotection.socialtracking.enabled"] = true
		prefs["privacy.trackingprotection.cryptomining.enabled"] = true
		prefs["privacy.trackingprotection.fingerprinting.enabled"] = true
		host, portText, err := net.SplitHostPort(proxy.Host)
		if err == nil {
			port, parseErr := strconv.Atoi(portText)
			if parseErr == nil {
				prefs["network.proxy.type"] = 1
				prefs["network.proxy.http"] = host
				prefs["network.proxy.http_port"] = port
				prefs["network.proxy.ssl"] = host
				prefs["network.proxy.ssl_port"] = port
				prefs["network.proxy.share_proxy_settings"] = true
				prefs["network.proxy.no_proxies_on"] = ""
				prefs["network.proxy.failover_direct"] = false
			}
		}
	}
	return prefs
}

func stopWebDriverProcessTree(pid int) error {
	if runtime.GOOS == "windows" {
		killCtx, cancel := context.WithTimeout(context.Background(), webDriverTreeKillTimeout)
		defer cancel()
		stop := exec.CommandContext(killCtx, "taskkill", "/T", "/F", "/PID", strconv.Itoa(pid))
		platform.HideConsole(stop)
		stop.Stdout = io.Discard
		stop.Stderr = io.Discard
		return stop.Run()
	}
	stop := exec.Command("kill", "-KILL", strconv.Itoa(pid))
	platform.HideConsole(stop)
	return stop.Run()
}

func seleniumFirefoxArgs() []string {
	headlessSetting := strings.ToLower(strings.TrimSpace(os.Getenv("ANIMECAOS_BROWSER_HEADLESS")))
	if headlessSetting == "0" || headlessSetting == "false" || headlessSetting == "no" {
		return []string{}
	}
	return []string{"-headless"}
}

func findFirefox() (string, error) {
	if configured := strings.TrimSpace(os.Getenv("ANIMECAOS_FIREFOX_PATH")); configured != "" {
		if info, err := os.Stat(configured); err == nil && !info.IsDir() {
			return configured, nil
		}
		return "", fmt.Errorf("Firefox configurado para Selenium não foi encontrado")
	}
	if path, err := findBundledFirefox(runtimeExecutableDir()); err == nil {
		return path, nil
	}
	for _, name := range []string{"firefox", "firefox.exe"} {
		if path, err := exec.LookPath(name); err == nil {
			return path, nil
		}
	}
	for _, path := range firefoxLocations() {
		if info, err := os.Stat(path); err == nil && !info.IsDir() {
			return path, nil
		}
	}
	return "", fmt.Errorf("Firefox não está instalado para usar Selenium com GeckoDriver")
}

func firefoxLocations() []string {
	switch runtime.GOOS {
	case "windows":
		programFiles := os.Getenv("ProgramFiles")
		programFilesX86 := os.Getenv("ProgramFiles(x86)")
		localAppData := os.Getenv("LOCALAPPDATA")
		return []string{
			programFiles + `\Mozilla Firefox\firefox.exe`,
			programFilesX86 + `\Mozilla Firefox\firefox.exe`,
			localAppData + `\Mozilla Firefox\firefox.exe`,
		}
	case "darwin":
		return []string{"/Applications/Firefox.app/Contents/MacOS/firefox"}
	default:
		return []string{"/usr/bin/firefox", "/usr/bin/firefox-esr", "/snap/bin/firefox"}
	}
}

func findBundledFirefox(executableDir string) (string, error) {
	for _, path := range bundledFirefoxLocations(executableDir, runtime.GOOS) {
		if info, err := os.Stat(path); err == nil && !info.IsDir() {
			return path, nil
		}
	}
	return "", fmt.Errorf("Firefox empacotado não foi encontrado")
}

func bundledFirefoxLocations(executableDir, goos string) []string {
	name := "firefox"
	if goos == "windows" {
		name += ".exe"
	}
	locations := []string{filepath.Join(executableDir, "bin", "firefox", name)}
	if goos == "linux" {
		locations = append(locations, filepath.Clean(filepath.Join(executableDir, "..", "lib", "firefox", name)))
	}
	return locations
}

func waitWebDriver(ctx context.Context, client *http.Client, base string) error {
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()
	for {
		request, err := http.NewRequestWithContext(ctx, http.MethodGet, base+"/status", nil)
		if err == nil {
			response, requestErr := client.Do(request)
			if requestErr == nil {
				response.Body.Close()
				if response.StatusCode == http.StatusOK {
					return nil
				}
			}
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
		}
	}
}

func webdriverCall(ctx context.Context, client *http.Client, method, endpoint string, payload any) (json.RawMessage, error) {
	var body io.Reader
	if payload != nil {
		encoded, err := json.Marshal(payload)
		if err != nil {
			return nil, err
		}
		body = bytes.NewReader(encoded)
	}
	request, err := http.NewRequestWithContext(ctx, method, endpoint, body)
	if err != nil {
		return nil, err
	}
	if payload != nil {
		request.Header.Set("Content-Type", "application/json")
	}
	response, err := client.Do(request)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	data, err := io.ReadAll(io.LimitReader(response.Body, maxWebdriverResponseSize))
	if err != nil {
		return nil, err
	}
	var value webdriverValue
	if json.Unmarshal(data, &value) == nil && value.Error != "" {
		return nil, fmt.Errorf("WebDriver %s: %s", value.Error, value.Message)
	}
	if len(value.Value) > 0 {
		var nested struct {
			Error   string `json:"error"`
			Message string `json:"message"`
		}
		if json.Unmarshal(value.Value, &nested) == nil && nested.Error != "" {
			return nil, fmt.Errorf("WebDriver %s: %s", nested.Error, nested.Message)
		}
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return nil, fmt.Errorf("WebDriver respondeu HTTP %d", response.StatusCode)
	}
	if len(value.Value) > 0 && string(value.Value) != "null" {
		return value.Value, nil
	}
	return data, nil
}
