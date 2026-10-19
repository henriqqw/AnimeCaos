package media

import (
	"context"
	"fmt"
	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

type Variant struct {
	URL       string
	Height    int
	Bandwidth int
	Codecs    string
}

var resolutionRE = regexp.MustCompile(`RESOLUTION=\d+x(\d+)`)
var bandwidthRE = regexp.MustCompile(`(?:^|,)BANDWIDTH=(\d+)`)
var codecsRE = regexp.MustCompile(`CODECS="([^"]+)"`)

func Variants(manifest, base string) []Variant {
	root, e := url.Parse(base)
	if e != nil {
		return nil
	}
	out := []Variant{}
	var current *Variant
	for _, line := range strings.Split(manifest, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "#EXT-X-STREAM-INF:") {
			v := Variant{}
			attrs := strings.TrimPrefix(line, "#EXT-X-STREAM-INF:")
			if m := resolutionRE.FindStringSubmatch(attrs); len(m) > 1 {
				v.Height, _ = strconv.Atoi(m[1])
			}
			if m := bandwidthRE.FindStringSubmatch(attrs); len(m) > 1 {
				v.Bandwidth, _ = strconv.Atoi(m[1])
			}
			if m := codecsRE.FindStringSubmatch(attrs); len(m) > 1 {
				v.Codecs = m[1]
			}
			current = &v
			continue
		}
		if current != nil && line != "" && !strings.HasPrefix(line, "#") {
			u, e := url.Parse(line)
			if e == nil {
				resolved := root.ResolveReference(u)
				if (resolved.Scheme == "http" || resolved.Scheme == "https") && !netx.IsAdvertisingURL(resolved.String()) {
					current.URL = resolved.String()
					out = append(out, *current)
				}
			}
			current = nil
		}
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Height != out[j].Height {
			return out[i].Height > out[j].Height
		}
		return out[i].Bandwidth > out[j].Bandwidth
	})
	return out
}

// Best chooses the highest available variant by manifest content, irrespective
// of URL extension. An unavailable variant falls back to the next resolution.
func Best(ctx context.Context, s domain.Stream) (domain.Stream, error) {
	if netx.IsAdvertisingURL(s.URL) {
		return s, fmt.Errorf("URL de anúncio ou rastreamento ignorada")
	}
	if s.Kind != "hls" {
		return s, nil
	}
	ctx, cancel := context.WithTimeout(ctx, 20*time.Second)
	defer cancel()
	req, e := http.NewRequestWithContext(ctx, "GET", s.URL, nil)
	if e != nil {
		return s, e
	}
	for k, v := range s.Headers {
		req.Header.Set(k, v)
	}
	if req.Header.Get("User-Agent") == "" {
		req.Header.Set("User-Agent", "Mozilla/5.0 AnimeCaos/3.0")
	}
	client := *http.DefaultClient
	configuredRedirectCheck := client.CheckRedirect
	client.CheckRedirect = func(request *http.Request, via []*http.Request) error {
		if err := netx.RejectAdvertisingRedirect(request, via); err != nil {
			return err
		}
		if configuredRedirectCheck != nil {
			return configuredRedirectCheck(request, via)
		}
		return nil
	}
	r, e := client.Do(req)
	if e != nil {
		return s, e
	}
	defer r.Body.Close()
	if r.StatusCode != 200 {
		if r.StatusCode == http.StatusNotFound {
			return s, fmt.Errorf("o servidor de vídeo não encontrou o arquivo deste episódio (HTTP 404)")
		}
		return s, fmt.Errorf("manifesto indisponível (HTTP %d)", r.StatusCode)
	}
	b, e := io.ReadAll(io.LimitReader(r.Body, 4<<20))
	if e != nil {
		return s, e
	}
	if !strings.HasPrefix(strings.TrimSpace(string(b)), "#EXTM3U") {
		return s, fmt.Errorf("a origem não retornou HLS")
	}
	variants := Variants(string(b), r.Request.URL.String())
	if len(variants) == 0 {
		return s, nil
	}
	var last error
	for _, v := range variants {
		candidate := s
		candidate.URL = v.URL
		candidate.Qualities = []string{fmt.Sprintf("%dp", v.Height)}
		candidate.Height = v.Height
		candidate.Bandwidth = v.Bandwidth
		if e = Validate(ctx, candidate); e == nil {
			return candidate, nil
		}
		last = e
	}
	return s, fmt.Errorf("variantes indisponíveis: %w", last)
}
