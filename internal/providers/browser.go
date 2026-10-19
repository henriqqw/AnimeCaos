package providers

import (
	"context"
	"fmt"
	"net/url"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"time"

	"github.com/chromedp/chromedp"
)

const renderedPlayerTimeout = 12 * time.Second

// renderedPlayerURLs runs only after HTTP scraping cannot find a usable player.
// It mirrors the legacy Selenium step by reading iframe.src after page scripts
// have run, while keeping each browser process bounded by the caller context.
func renderedPlayerURLs(ctx context.Context, pageURL string) ([]playerURLCandidate, error) {
	seleniumDriver := seleniumDriverPath()
	if configured := strings.TrimSpace(os.Getenv("ANIMECAOS_GECKODRIVER_PATH")); configured != "" && seleniumDriver == "" {
		return nil, fmt.Errorf("GeckoDriver configurado para Selenium não foi encontrado")
	}
	proxy, closeProxy, err := startBrowserAdProxy()
	if err != nil {
		return nil, fmt.Errorf("não foi possível iniciar o filtro de anúncios do navegador: %w", err)
	}
	defer closeProxy()
	ctx, cancel := context.WithTimeout(ctx, renderedPlayerTimeout)
	defer cancel()
	if seleniumDriver != "" {
		return seleniumPlayerURLs(ctx, pageURL, seleniumDriver, proxy)
	}
	browserPath, err := findBrowser()
	if err != nil {
		return nil, err
	}

	options := append([]chromedp.ExecAllocatorOption{}, chromedp.DefaultExecAllocatorOptions[:]...)
	options = append(options,
		chromedp.ExecPath(browserPath),
		chromedp.DisableGPU,
		chromedp.Flag("disable-background-networking", true),
		chromedp.Flag("disable-notifications", true),
	)
	if proxy != nil {
		options = append(options, chromedp.ProxyServer(proxy.String()))
	}
	if headlessSetting := strings.ToLower(strings.TrimSpace(os.Getenv("ANIMECAOS_BROWSER_HEADLESS"))); headlessSetting == "0" || headlessSetting == "false" || headlessSetting == "no" {
		options = append(options, chromedp.Flag("headless", false))
	}
	allocCtx, cancelAllocator := chromedp.NewExecAllocator(ctx, options...)
	defer cancelAllocator()
	browserCtx, cancelBrowser := chromedp.NewContext(allocCtx)
	defer cancelBrowser()

	inspectReady := `(() => { const state = ` + renderedPlayerInspectScript + `; window.__animecaosRenderedPlayer = state; return state.blocked || state.adInterstitial || state.urls.length > 0; })()`
	var ready bool
	if err := chromedp.Run(browserCtx,
		chromedp.Navigate(pageURL),
		chromedp.WaitReady("body", chromedp.ByQuery),
		chromedp.Poll(inspectReady, &ready,
			chromedp.WithPollingInterval(250*time.Millisecond),
			chromedp.WithPollingTimeout(8*time.Second)),
	); err != nil {
		var diagnostics struct {
			ReadyState    string `json:"readyState"`
			JWPlayer      string `json:"jwplayer"`
			PlayerElement bool   `json:"playerElement"`
			VideoCount    int    `json:"videoCount"`
			ScriptCount   int    `json:"scriptCount"`
			LocationHost  string `json:"locationHost"`
			Title         string `json:"title"`
			BlockedText   bool   `json:"blockedText"`
		}
		_ = chromedp.Run(browserCtx, chromedp.Evaluate(`({readyState:document.readyState,jwplayer:typeof window.jwplayer,playerElement:!!document.querySelector('#video_player'),videoCount:document.querySelectorAll('video').length,scriptCount:document.scripts.length,locationHost:location.hostname,title:document.title,blockedText:/forbidden|blocked|cloudflare|security verification/i.test(document.body?.innerText||'')})`, &diagnostics))
		requestedHost := ""
		if parsed, parseErr := url.Parse(pageURL); parseErr == nil {
			requestedHost = parsed.Hostname()
		}
		return nil, fmt.Errorf("navegação do player com JavaScript: %w (requestedHost=%s actualHost=%s title=%q readyState=%s jwplayer=%s playerElement=%t videos=%d scripts=%d blockedText=%t)", err, requestedHost, diagnostics.LocationHost, diagnostics.Title, diagnostics.ReadyState, diagnostics.JWPlayer, diagnostics.PlayerElement, diagnostics.VideoCount, diagnostics.ScriptCount, diagnostics.BlockedText)
	}

	var state renderedPlayerState
	if err := chromedp.Run(browserCtx, chromedp.Evaluate("window.__animecaosRenderedPlayer", &state)); err != nil {
		return nil, fmt.Errorf("leitura do player renderizado: %w", err)
	}
	if state.Blocked {
		return nil, fmt.Errorf("página do player permaneceu em verificação de segurança")
	}
	if state.AdInterstitial {
		return nil, fmt.Errorf("player protegido por intersticial de anúncio; nenhum link publicitário foi aberto")
	}
	return uniquePlayerCandidates(state.URLs), nil
}

func securityChallenge(body string) bool {
	value := strings.ToLower(body)
	for _, marker := range []string{"performing security verification", "checking your browser", "checking if the site connection is secure", "verificação de segurança", "bot detected", "cf-chl-", "cloudflare ray id", "just a moment"} {
		if strings.Contains(value, marker) {
			return true
		}
	}
	return false
}

func seleniumDriverPath() string {
	var seleniumDriver string
	if driverPath := strings.TrimSpace(os.Getenv("ANIMECAOS_GECKODRIVER_PATH")); driverPath != "" {
		if _, err := os.Stat(driverPath); err != nil {
			return ""
		}
		seleniumDriver = driverPath
	}
	if seleniumDriver == "" {
		if driverPath, err := exec.LookPath("geckodriver"); err == nil {
			// A GeckoDriver on PATH does not imply Firefox is installed. In that
			// case keep the optional Selenium path from masking an available
			// Chromium browser.
			if _, firefoxErr := findFirefox(); firefoxErr == nil {
				seleniumDriver = driverPath
			}
		}
	}
	return seleniumDriver
}

func findBrowser() (string, error) {
	if configured := strings.TrimSpace(os.Getenv("ANIMECAOS_BROWSER_PATH")); configured != "" {
		if _, err := os.Stat(configured); err == nil {
			return configured, nil
		}
		return "", fmt.Errorf("o navegador configurado para o scraper não foi encontrado")
	}
	for _, name := range []string{"chrome", "chrome.exe", "msedge", "msedge.exe", "chromium", "chromium-browser"} {
		if path, err := exec.LookPath(name); err == nil {
			return path, nil
		}
	}
	for _, path := range browserLocations() {
		if _, err := os.Stat(path); err == nil {
			return path, nil
		}
	}
	return "", fmt.Errorf("não há Chromium, Chrome ou Edge instalado para abrir o player dinâmico")
}

func uniqueURLs(urls []string) []string {
	seen := make(map[string]bool, len(urls))
	out := make([]string, 0, len(urls))
	for _, raw := range urls {
		key := strings.TrimSpace(raw)
		if key == "" || seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, key)
	}
	return out
}

func browserLocations() []string {
	switch runtime.GOOS {
	case "windows":
		programFiles := os.Getenv("ProgramFiles")
		programFilesX86 := os.Getenv("ProgramFiles(x86)")
		localAppData := os.Getenv("LOCALAPPDATA")
		return []string{
			programFilesX86 + `\Google\Chrome\Application\chrome.exe`,
			programFiles + `\Google\Chrome\Application\chrome.exe`,
			localAppData + `\Google\Chrome\Application\chrome.exe`,
			programFilesX86 + `\Microsoft\Edge\Application\msedge.exe`,
			programFiles + `\Microsoft\Edge\Application\msedge.exe`,
			localAppData + `\Microsoft\Edge\Application\msedge.exe`,
		}
	case "darwin":
		return []string{
			"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
			"/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
			"/Applications/Chromium.app/Contents/MacOS/Chromium",
		}
	default:
		return []string{"/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser", "/snap/bin/chromium"}
	}
}
