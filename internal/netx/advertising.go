package netx

import (
	"errors"
	"net/http"
	"net/url"
	"strings"
)

var advertisingHosts = []string{
	"t.dtscout.com",
	"crwdcntrl.net",
	"doubleclick.net",
	"googlesyndication.com",
	"googleadservices.com",
	"googletagmanager.com",
	"google-analytics.com",
	"adnxs.com",
	"adsrvr.org",
	"taboola.com",
	"outbrain.com",
	"popads.net",
	"popcash.net",
	"waust.at",
	"21wiz.com",
}

// IsAdvertisingURL identifies known ad and analytics hosts by exact DNS suffix.
// It intentionally does not filter by URL path or query, avoiding false
// positives for signed media URLs hosted on ordinary CDNs.
func IsAdvertisingURL(raw string) bool {
	parsed, err := url.Parse(raw)
	if err != nil {
		return true
	}
	return IsAdvertisingHost(parsed.Hostname())
}

func IsAdvertisingHost(rawHost string) bool {
	host := strings.TrimPrefix(strings.ToLower(strings.TrimSpace(rawHost)), "www.")
	if host == "" {
		return true
	}
	for _, blocked := range advertisingHosts {
		if host == blocked || strings.HasSuffix(host, "."+blocked) {
			return true
		}
	}
	return false
}

// RejectAdvertisingRedirect is an http.Client CheckRedirect callback. Returning
// ErrUseLastResponse leaves the 3xx response with the caller while preventing
// the HTTP client from following its Location header.
func RejectAdvertisingRedirect(request *http.Request, via []*http.Request) error {
	if request != nil && request.URL != nil && IsAdvertisingURL(request.URL.String()) {
		return http.ErrUseLastResponse
	}
	if len(via) >= 10 {
		return errors.New("stopped after 10 redirects")
	}
	return nil
}
