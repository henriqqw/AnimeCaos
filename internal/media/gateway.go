// Package media provides local, bounded HTTP sessions for remote media. Rewriting
// manifests avoids relying on misleading CDN suffixes such as AnimeFire's .jpg.
package media

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
	"io"
	"net"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"sync"
	"time"
)

type target struct {
	URL          string
	Headers      map[string]string
	Session      string
	Alternatives []string
}
type Gateway struct {
	mu       sync.Mutex
	targets  map[string]target
	archives map[string]archivePage
	server   *http.Server
	base     string
	client   *http.Client
}

func ID() string {
	var b [16]byte
	_, e := rand.Read(b[:])
	if e != nil {
		panic(e)
	}
	return hex.EncodeToString(b[:])
}
func NewGateway() (*Gateway, error) {
	l, e := net.Listen("tcp", "127.0.0.1:0")
	if e != nil {
		return nil, e
	}
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.ResponseHeaderTimeout = 30 * time.Second
	g := &Gateway{targets: map[string]target{}, archives: map[string]archivePage{}, base: "http://" + l.Addr().String(), client: &http.Client{Transport: transport, CheckRedirect: netx.RejectAdvertisingRedirect}}
	g.server = &http.Server{Handler: http.HandlerFunc(g.serve), ReadHeaderTimeout: 5 * time.Second}
	go g.server.Serve(l)
	return g, nil
}
func (g *Gateway) Close() error { return g.server.Close() }
func (g *Gateway) Register(s domain.Stream) (string, func()) {
	session := ID()
	ext := "file.mp4"
	if s.Kind == "hls" {
		ext = "master.m3u8"
	}
	u := g.add(s.URL, s.Headers, session, ext)
	return u, func() {
		g.mu.Lock()
		defer g.mu.Unlock()
		for k, t := range g.targets {
			if t.Session == session {
				delete(g.targets, k)
			}
		}
	}
}
func (g *Gateway) add(u string, h map[string]string, session, ext string) string {
	key := ID() + "/" + ext
	g.mu.Lock()
	for existing, t := range g.targets {
		if t.Session == session && t.URL == u {
			g.mu.Unlock()
			return g.base + "/media/" + existing
		}
	}
	g.targets[key] = target{URL: u, Headers: h, Session: session}
	g.mu.Unlock()
	return g.base + "/media/" + key
}

func (g *Gateway) RegisterImage(primary string, alternatives []string) (string, func()) {
	u, release := g.Register(domain.Stream{URL: primary})
	key := strings.TrimPrefix(u, g.base+"/media/")
	g.mu.Lock()
	t := g.targets[key]
	t.Alternatives = append([]string{}, alternatives...)
	g.targets[key] = t
	g.mu.Unlock()
	return u, release
}

var uriRE = regexp.MustCompile(`URI="([^"]+)"`)

func (g *Gateway) rewrite(manifest, base string, t target) string {
	baseURL, _ := url.Parse(base)
	resolve := func(ref, ext string) string {
		u, e := url.Parse(ref)
		if e != nil {
			return ""
		}
		u = baseURL.ResolveReference(u)
		if u.Scheme != "https" && u.Scheme != "http" {
			return ""
		}
		return g.add(u.String(), t.Headers, t.Session, ext)
	}
	lines := strings.Split(manifest, "\n")
	variant := false
	for i, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if strings.HasPrefix(line, "#") {
			if strings.HasPrefix(line, "#EXT-X-STREAM-INF:") {
				variant = true
			}
			ext := "playlist.m3u8"
			if strings.HasPrefix(line, "#EXT-X-KEY:") {
				ext = "key.bin"
			}
			if strings.HasPrefix(line, "#EXT-X-MAP:") {
				ext = "init.mp4"
			}
			lines[i] = uriRE.ReplaceAllStringFunc(line, func(s string) string { m := uriRE.FindStringSubmatch(s); return `URI="` + resolve(m[1], ext) + `"` })
		} else {
			ext := "segment.ts"
			if variant {
				ext = "variant.m3u8"
				variant = false
			}
			lines[i] = resolve(line, ext)
		}
	}
	return strings.Join(lines, "\n")
}
func (g *Gateway) serve(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" && r.Method != "HEAD" {
		w.WriteHeader(405)
		return
	}
	if strings.HasPrefix(r.URL.Path, "/archive/") {
		g.serveArchive(w, r)
		return
	}
	key := strings.TrimPrefix(r.URL.Path, "/media/")
	g.mu.Lock()
	t, ok := g.targets[key]
	g.mu.Unlock()
	if !ok {
		http.NotFound(w, r)
		return
	}
	var resp *http.Response
	var e error
	for i, u := range append([]string{t.URL}, t.Alternatives...) {
		if netx.IsAdvertisingURL(u) {
			e = fmt.Errorf("URL de anúncio ou rastreamento ignorada")
			continue
		}
		req, err := http.NewRequestWithContext(r.Context(), r.Method, u, nil)
		if err != nil {
			e = err
			continue
		}
		for k, v := range t.Headers {
			req.Header.Set(k, v)
		}
		if req.Header.Get("User-Agent") == "" {
			req.Header.Set("User-Agent", "Mozilla/5.0 AnimeCaos/3.0")
		}
		if v := r.Header.Get("Range"); v != "" {
			req.Header.Set("Range", v)
		}
		resp, e = g.client.Do(req)
		if e == nil && resp.StatusCode >= 200 && resp.StatusCode < 300 {
			break
		}
		if resp != nil && netx.IsAdvertisingURL(resp.Header.Get("Location")) {
			resp.Body.Close()
			resp = nil
			e = fmt.Errorf("redirecionamento para anúncio ou rastreador bloqueado")
			continue
		}
		if resp != nil && i < len(t.Alternatives) {
			resp.Body.Close()
		}
	}
	if e != nil {
		http.Error(w, "fonte indisponível", 502)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		w.WriteHeader(resp.StatusCode)
		return
	}
	reader := bufio.NewReader(resp.Body)
	prefix, _ := reader.Peek(16)
	if strings.HasPrefix(strings.TrimSpace(string(prefix)), "#EXTM3U") {
		b, e := io.ReadAll(io.LimitReader(reader, 4<<20))
		if e != nil {
			http.Error(w, "manifesto inválido", 502)
			return
		}
		w.Header().Set("Content-Type", "application/vnd.apple.mpegurl")
		io.WriteString(w, g.rewrite(string(b), resp.Request.URL.String(), t))
		return
	}
	for _, k := range []string{"Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"} {
		if v := resp.Header.Get(k); v != "" {
			w.Header().Set(k, v)
		}
	}
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, reader)
}
func Validate(ctx context.Context, s domain.Stream) error {
	if netx.IsAdvertisingURL(s.URL) {
		return fmt.Errorf("URL de anúncio ou rastreamento ignorada")
	}
	r, e := http.NewRequestWithContext(ctx, "GET", s.URL, nil)
	if e != nil {
		return e
	}
	for k, v := range s.Headers {
		r.Header.Set(k, v)
	}
	if r.Header.Get("User-Agent") == "" {
		r.Header.Set("User-Agent", "Mozilla/5.0 AnimeCaos/3.0")
	}
	r.Header.Set("Range", "bytes=0-1023")
	client := http.Client{Timeout: 12 * time.Second, CheckRedirect: netx.RejectAdvertisingRedirect}
	resp, e := client.Do(r)
	if e != nil {
		return e
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("vídeo indisponível na origem (HTTP %d)", resp.StatusCode)
	}
	b, e := io.ReadAll(io.LimitReader(resp.Body, 1024))
	if e != nil {
		return e
	}
	if s.Kind == "hls" && !strings.HasPrefix(strings.TrimSpace(string(b)), "#EXTM3U") {
		return fmt.Errorf("a origem não retornou um manifesto HLS")
	}
	if len(b) == 0 {
		return fmt.Errorf("vídeo vazio")
	}
	return nil
}
