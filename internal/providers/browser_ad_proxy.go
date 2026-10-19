package providers

import (
	"context"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// startBrowserAdProxy starts a loopback-only proxy for a short-lived scraper
// browser. HTTPS is tunneled unchanged; only requests to known advertising and
// analytics hosts are rejected before their scripts can run. Public
// player/media hosts continue through the proxy unchanged.
func startBrowserAdProxy() (*url.URL, func(), error) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, nil, err
	}
	server := &http.Server{
		Handler:           browserAdProxy{transport: &http.Transport{Proxy: nil}},
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() { _ = server.Serve(listener) }()
	endpoint, err := url.Parse("http://" + listener.Addr().String())
	if err != nil {
		_ = server.Close()
		return nil, nil, err
	}
	closeProxy := func() {
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		defer cancel()
		_ = server.Shutdown(ctx)
		if transport, ok := server.Handler.(browserAdProxy); ok && transport.transport != nil {
			transport.transport.CloseIdleConnections()
		}
	}
	return endpoint, closeProxy, nil
}

type browserAdProxy struct {
	transport *http.Transport
}

func (p browserAdProxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodConnect {
		p.serveConnect(w, r)
		return
	}
	if r.URL == nil || (r.URL.Scheme != "http" && r.URL.Scheme != "https") || r.URL.Host == "" {
		http.Error(w, "proxy requires an absolute HTTP(S) URL", http.StatusBadRequest)
		return
	}
	if isAdvertisingHost(r.URL.Hostname()) {
		http.Error(w, "known advertising or tracking host blocked by AnimeCaos", http.StatusForbidden)
		return
	}
	request := r.Clone(r.Context())
	request.RequestURI = ""
	request.Header.Del("Proxy-Connection")
	request.Header.Del("Proxy-Authorization")
	response, err := p.transport.RoundTrip(request)
	if err != nil {
		http.Error(w, "upstream request failed", http.StatusBadGateway)
		return
	}
	defer response.Body.Close()
	for key, values := range response.Header {
		for _, value := range values {
			w.Header().Add(key, value)
		}
	}
	w.WriteHeader(response.StatusCode)
	_, _ = io.Copy(w, response.Body)
}

func (p browserAdProxy) serveConnect(w http.ResponseWriter, r *http.Request) {
	host := r.Host
	if parsed, _, err := net.SplitHostPort(host); err == nil {
		host = parsed
	} else {
		host = strings.Trim(host, "[]")
	}
	if isAdvertisingHost(host) {
		http.Error(w, "known advertising or tracking host blocked by AnimeCaos", http.StatusForbidden)
		return
	}
	upstream, err := (&net.Dialer{Timeout: 8 * time.Second}).DialContext(r.Context(), "tcp", r.Host)
	if err != nil {
		http.Error(w, "upstream connection failed", http.StatusBadGateway)
		return
	}
	hijacker, ok := w.(http.Hijacker)
	if !ok {
		_ = upstream.Close()
		http.Error(w, "CONNECT is not supported", http.StatusInternalServerError)
		return
	}
	client, buffered, err := hijacker.Hijack()
	if err != nil {
		_ = upstream.Close()
		return
	}
	if _, err = fmt.Fprint(buffered, "HTTP/1.1 200 Connection Established\r\n\r\n"); err != nil {
		_ = client.Close()
		_ = upstream.Close()
		return
	}
	if err = buffered.Flush(); err != nil {
		_ = client.Close()
		_ = upstream.Close()
		return
	}
	closed := make(chan struct{}, 1)
	go func() {
		_, _ = io.Copy(upstream, buffered.Reader)
		_ = upstream.Close()
		closed <- struct{}{}
	}()
	_, _ = io.Copy(client, upstream)
	_ = client.Close()
	_ = upstream.Close()
	<-closed
}
