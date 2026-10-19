package providers

import (
	"bufio"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
)

func TestBrowserAdProxyBlocksKnownTrackerButPassesPlayerRequests(t *testing.T) {
	proxyURL, closeProxy, err := startBrowserAdProxy()
	if err != nil {
		t.Fatal(err)
	}
	defer closeProxy()

	var forwarded int
	player := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		forwarded++
		w.Header().Set("Content-Type", "application/vnd.apple.mpegurl")
		_, _ = io.WriteString(w, "#EXTM3U\n")
	}))
	defer player.Close()

	transport := &http.Transport{Proxy: http.ProxyURL(proxyURL)}
	defer transport.CloseIdleConnections()
	client := &http.Client{Transport: transport}
	response, err := client.Get(player.URL + "/episode.m3u8")
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	if response.StatusCode != http.StatusOK || forwarded != 1 {
		t.Fatalf("player request was not passed through: status=%d forwarded=%d", response.StatusCode, forwarded)
	}

	tracker, err := client.Get("http://tags.crwdcntrl.net/pixel")
	if err != nil {
		t.Fatal(err)
	}
	tracker.Body.Close()
	if tracker.StatusCode != http.StatusForbidden || forwarded != 1 {
		t.Fatalf("tracker was not blocked before network access: status=%d forwarded=%d", tracker.StatusCode, forwarded)
	}
}

func TestBrowserAdProxyBlocksTrackerCONNECTBeforeTunnel(t *testing.T) {
	proxyURL, closeProxy, err := startBrowserAdProxy()
	if err != nil {
		t.Fatal(err)
	}
	defer closeProxy()

	conn, err := net.Dial("tcp", proxyURL.Host)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	if _, err := fmt.Fprintf(conn, "CONNECT t.dtscout.com:443 HTTP/1.1\r\nHost: t.dtscout.com:443\r\n\r\n"); err != nil {
		t.Fatal(err)
	}
	response, err := http.ReadResponse(bufio.NewReader(conn), &http.Request{Method: http.MethodConnect})
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	if response.StatusCode != http.StatusForbidden {
		t.Fatalf("tracker tunnel status = %d, want %d", response.StatusCode, http.StatusForbidden)
	}
}

func TestProxyURLContainsLoopbackOnlyHost(t *testing.T) {
	proxyURL, closeProxy, err := startBrowserAdProxy()
	if err != nil {
		t.Fatal(err)
	}
	defer closeProxy()
	parsed, err := url.Parse(proxyURL.String())
	if err != nil {
		t.Fatal(err)
	}
	if parsed.Hostname() != "127.0.0.1" || !strings.HasPrefix(parsed.Scheme, "http") {
		t.Fatalf("browser ad filter proxy is not loopback-only HTTP: %s", proxyURL)
	}
}
