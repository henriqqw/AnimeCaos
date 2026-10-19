package netx

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"sync"
	"time"
)

type HTTPError struct {
	Status     int
	RetryAfter time.Duration
	Code       string
	Body       []byte `json:"-"`
}

func (e *HTTPError) Error() string {
	if e.Code == "invalid_client" {
		return "cliente OAuth recusado (invalid_client): confira o tipo do aplicativo e o Client ID"
	}
	if e.Code == "invalid_grant" {
		return "código de autorização inválido ou expirado (invalid_grant); inicie um novo login"
	}
	switch e.Status {
	case 404:
		return "conteúdo não encontrado (404)"
	case 401:
		return "autenticação expirada (401)"
	case 403:
		return "acesso recusado pela fonte (403)"
	case 429:
		return "limite de requisições atingido (429)"
	}
	return fmt.Sprintf("fonte respondeu HTTP %d", e.Status)
}

type Client struct {
	HTTP *http.Client
	mu   sync.Mutex
	next map[string]time.Time
}

func New() *Client {
	return &Client{HTTP: &http.Client{Timeout: 20 * time.Second}, next: map[string]time.Time{}}
}

// Stream bounds connection setup while allowing large bodies to run for the
// lifetime chosen by the caller's context instead of the API's 20 second limit.
func (c *Client) Stream(ctx context.Context, url string, headers map[string]string) (*http.Response, error) {
	client := *c.HTTP
	client.Timeout = 0
	if client.Transport == nil {
		transport := http.DefaultTransport.(*http.Transport).Clone()
		transport.ResponseHeaderTimeout = 30 * time.Second
		client.Transport = transport
	}
	transfer := &Client{HTTP: &client, next: map[string]time.Time{}}
	return transfer.Do(ctx, "GET", url, nil, headers)
}
func (c *Client) Do(ctx context.Context, method, url string, body []byte, headers map[string]string) (*http.Response, error) {
	httpClient := *c.HTTP
	configuredRedirectCheck := httpClient.CheckRedirect
	httpClient.CheckRedirect = func(request *http.Request, via []*http.Request) error {
		if err := RejectAdvertisingRedirect(request, via); err != nil {
			return err
		}
		if configuredRedirectCheck != nil {
			return configuredRedirectCheck(request, via)
		}
		return nil
	}
	for attempt := 0; attempt < 3; attempt++ {
		req, e := http.NewRequestWithContext(ctx, method, url, bytes.NewReader(body))
		if e != nil {
			return nil, e
		}
		req.Header.Set("User-Agent", "Mozilla/5.0 AnimeCaos/3.0")
		for k, v := range headers {
			req.Header.Set(k, v)
		}
		host := req.URL.Host
		c.mu.Lock()
		wait := time.Until(c.next[host])
		c.mu.Unlock()
		if wait > 0 {
			if e = sleep(ctx, wait); e != nil {
				return nil, e
			}
		}
		r, e := httpClient.Do(req)
		if e != nil {
			return nil, fmt.Errorf("falha de conexão: %w", e)
		}
		if r.StatusCode >= 200 && r.StatusCode < 300 {
			return r, nil
		}
		errorBody, _ := io.ReadAll(io.LimitReader(r.Body, 8192))
		r.Body.Close()
		var apiError struct {
			Code string `json:"error"`
		}
		json.Unmarshal(errorBody, &apiError)
		code := ""
		if apiError.Code == "invalid_client" || apiError.Code == "invalid_grant" {
			code = apiError.Code
		}
		delay := time.Duration(attempt+1) * 300 * time.Millisecond
		if r.StatusCode == 429 {
			seconds, _ := strconv.Atoi(r.Header.Get("Retry-After"))
			if seconds < 1 {
				seconds = 60
			}
			delay = time.Duration(seconds) * time.Second
			c.mu.Lock()
			c.next[host] = time.Now().Add(delay)
			c.mu.Unlock()
			return nil, &HTTPError{Status: r.StatusCode, RetryAfter: delay}
		}
		if method != "GET" || r.StatusCode < 500 || attempt == 2 {
			return nil, &HTTPError{Status: r.StatusCode, Code: code, Body: errorBody}
		}
		if e = sleep(ctx, delay); e != nil {
			return nil, e
		}
	}
	return nil, fmt.Errorf("fonte indisponível")
}
func (c *Client) JSON(ctx context.Context, method, url string, body any, headers map[string]string, out any) error {
	var b []byte
	var e error
	if body != nil {
		b, e = json.Marshal(body)
		if e != nil {
			return e
		}
	}
	h := map[string]string{"Accept": "application/json", "Content-Type": "application/json"}
	for k, v := range headers {
		h[k] = v
	}
	r, e := c.Do(ctx, method, url, b, h)
	if e != nil {
		return e
	}
	defer r.Body.Close()
	if e = json.NewDecoder(io.LimitReader(r.Body, 16<<20)).Decode(out); e != nil {
		return fmt.Errorf("formato inesperado da fonte: %w", e)
	}
	return nil
}
func sleep(ctx context.Context, d time.Duration) error {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}

// Gate reserves request times without holding a lock while callers wait.
type Gate struct {
	mu       sync.Mutex
	next     time.Time
	Interval time.Duration
}

func (g *Gate) Wait(ctx context.Context) error {
	g.mu.Lock()
	now := time.Now()
	at := g.next
	if at.Before(now) {
		at = now
	}
	g.next = at.Add(g.Interval)
	g.mu.Unlock()
	return sleep(ctx, time.Until(at))
}
