package providers

import (
	"context"
	"encoding/hex"
	"fmt"
	"github.com/PuerkitoBio/goquery"
	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
	"html"
	"io"
	"net/url"
	"path"
	"regexp"
	"strconv"
	"strings"
)

type OnlineCC struct {
	Client *netx.Client
	Base   string
}

func NewOnlineCC(c *netx.Client) *OnlineCC {
	return &OnlineCC{Client: c, Base: "https://animesonlinecc.to"}
}
func (p *OnlineCC) Name() string { return "animesonlinecc" }
func (p *OnlineCC) doc(ctx context.Context, u string) (*goquery.Document, error) {
	r, e := p.Client.Do(ctx, "GET", u, nil, nil)
	if e != nil {
		return nil, e
	}
	defer r.Body.Close()
	return goquery.NewDocumentFromReader(io.LimitReader(r.Body, 8<<20))
}
func absolute(base, ref string) string {
	u, e := url.Parse(base)
	if e != nil {
		return ""
	}
	r, e := url.Parse(ref)
	if e != nil {
		return ""
	}
	v := u.ResolveReference(r)
	if v.Scheme != "http" && v.Scheme != "https" {
		return ""
	}
	return v.String()
}
func (p *OnlineCC) Search(ctx context.Context, q string, page int) (domain.SearchResult, error) {
	out := domain.SearchResult{Items: []domain.Anime{}, Page: page, Warnings: []string{}}
	u := p.Base + "/search/" + strings.ReplaceAll(url.QueryEscape(q), "%20", "+")
	if page > 1 {
		u += "/page/" + strconv.Itoa(page) + "/"
	}
	doc, e := p.doc(ctx, u)
	if e != nil {
		return out, e
	}
	seen := map[string]bool{}
	doc.Find(".items .item, .items article, article, .result-item, .item").Each(func(_ int, card *goquery.Selection) {
		s := card.Find(".data h3 a, .data a[href], h3 a[href], a.series[href]").First()
		if s.Length() == 0 {
			s = card.Find("a[href]").First()
		}
		href, _ := s.Attr("href")
		href = absolute(p.Base, href)
		title := strings.TrimSpace(s.Text())
		if href != "" && title != "" && !seen[href] {
			seen[href] = true
			cover, _ := card.Find("img").First().Attr("data-src")
			if cover == "" {
				cover, _ = card.Find("img").First().Attr("src")
			}
			out.Items = append(out.Items, domain.Anime{ID: href, Provider: p.Name(), Title: title, URL: href, Cover: absolute(p.Base, cover)})
		}
	})
	// Some theme variants do not wrap results in cards. Keep a bounded fallback
	// for the title links used by the catalog without treating navigation as anime.
	doc.Find(".data h3 a[href], h3 a.series[href]").Each(func(_ int, s *goquery.Selection) {
		href, _ := s.Attr("href")
		href = absolute(p.Base, href)
		title := strings.TrimSpace(s.Text())
		if href != "" && title != "" && !seen[href] {
			seen[href] = true
			out.Items = append(out.Items, domain.Anime{ID: href, Provider: p.Name(), Title: title, URL: href})
		}
	})
	out.HasNext = doc.Find("a.next, .pagination .next").Length() > 0
	return out, nil
}

var numberRE = regexp.MustCompile(`(?i)(?:epis[oó]dio|episode|ep)[\s-]*(\d+(?:\.\d+)?)`)
var plainNumberRE = regexp.MustCompile(`\d+(?:\.\d+)?`)

func (p *OnlineCC) Details(ctx context.Context, a domain.Anime) (domain.Detail, error) {
	doc, e := p.doc(ctx, a.URL)
	if e != nil {
		return domain.Detail{}, e
	}
	d := domain.Detail{Anime: a, Episodes: []domain.Episode{}}
	if d.Anime.Title == "" {
		d.Anime.Title = strings.TrimSpace(doc.Find(".data h1, h1").First().Text())
	}
	if d.Anime.Cover == "" {
		d.Anime.Cover, _ = doc.Find(".poster img").First().Attr("src")
	}
	doc.Find("ul.episodios").Each(func(_ int, s *goquery.Selection) {
		season := 0
		seasonLabel := strings.TrimSpace(s.Closest(".se-a").PrevAll().First().Find(".se-t").Text())
		if seasonLabel == "" {
			seasonLabel = strings.TrimSpace(s.Closest(".se-c").Find(".se-q .se-t").First().Text())
		}
		if n, err := strconv.Atoi(strings.TrimSpace(seasonLabel)); err == nil && n > 0 {
			season = n
		}
		s.Find(".episodiotitle a").Each(func(_ int, link *goquery.Selection) {
			href, _ := link.Attr("href")
			href = absolute(a.URL, href)
			title := strings.TrimSpace(link.Text())
			n := float64(0)
			numberText := strings.TrimSpace(link.Closest("li").Find(".numerando").First().Text())
			if m := numberRE.FindStringSubmatch(numberText + " " + title); len(m) > 1 {
				n, _ = strconv.ParseFloat(m[1], 64)
			} else if m := plainNumberRE.FindString(numberText); m != "" {
				n, _ = strconv.ParseFloat(m, 64)
			} else if m := numberRE.FindStringSubmatch(title); len(m) > 1 {
				n, _ = strconv.ParseFloat(m[1], 64)
			}
			if href != "" {
				d.Episodes = append(d.Episodes, domain.Episode{ID: href, URL: href, AnimeID: a.ID, Provider: p.Name(), Title: title, Number: n, Season: season})
			}
		})
	})
	d.Anime.Description = strings.TrimSpace(doc.Find(".wp-content p").First().Text())
	d.Anime.EpisodeCount = len(d.Episodes)
	if len(d.Episodes) == 0 {
		return d, fmt.Errorf("nenhum episódio encontrado nesta fonte")
	}
	return d, nil
}

var jsMedia = regexp.MustCompile(`(?i)(?:file|src|source)["']?\s*[:=]\s*["']((?:https?:|\\uhttps?:|\\x68ttps?:)[^"']+)["']`)

// decodeScrapedURL mirrors the URL Selenium exposes for iframe.src in the
// legacy scraper: HTML entities and common JavaScript string escapes are
// decoded before a URL is handed to the player resolver.
func decodeScrapedURL(raw string) string {
	raw = html.UnescapeString(strings.TrimSpace(raw))
	raw = strings.ReplaceAll(raw, `\/`, `/`)
	raw = strings.ReplaceAll(raw, `\:`, `:`)
	raw = strings.ReplaceAll(raw, `\&`, `&`)
	var b strings.Builder
	for i := 0; i < len(raw); {
		if i+4 <= len(raw) && raw[i:i+2] == `\x` {
			if value, err := hex.DecodeString(raw[i+2 : i+4]); err == nil {
				b.Write(value)
				i += 4
				continue
			}
		}
		if i+6 <= len(raw) && raw[i:i+2] == `\u` {
			if value, err := hex.DecodeString(raw[i+2 : i+6]); err == nil {
				b.WriteRune(rune(value[0])<<8 | rune(value[1]))
				i += 6
				continue
			}
		}
		b.WriteByte(raw[i])
		i++
	}
	return strings.TrimSpace(b.String())
}

func scrapedHTTPURL(base, raw string) string {
	parsed, err := url.Parse(decodeScrapedURL(raw))
	if err != nil {
		return ""
	}
	resolved, err := url.Parse(base)
	if err != nil {
		return ""
	}
	parsed = resolved.ResolveReference(parsed)
	if (parsed.Scheme != "http" && parsed.Scheme != "https") || parsed.Host == "" {
		return ""
	}
	return parsed.String()
}

func (p *OnlineCC) Resolve(ctx context.Context, ep domain.Episode) ([]domain.Stream, error) {
	doc, err := p.doc(ctx, ep.URL)
	if err != nil {
		return nil, err
	}
	options := doc.Find(".sourceslist a[href^='#'], .options a[href^='#']")
	if options.Length() == 0 {
		return p.resolvePage(ctx, ep.URL, ep.URL, 0)
	}
	streams := []domain.Stream{}
	options.Each(func(_ int, option *goquery.Selection) {
		if ctx.Err() != nil {
			return
		}
		href, _ := option.Attr("href")
		id := strings.TrimPrefix(href, "#")
		frameElement := doc.Find("#" + id + " iframe[src], #" + id + " video[src], #" + id + " source[src]").First()
		frame, ok := frameElement.Attr("src")
		if !ok {
			return
		}
		frame = absolute(ep.URL, frame)
		if frame == "" {
			return
		}
		policy, _ := frameElement.Attr("referrerpolicy")
		referer := playerReferer(ep.URL, frame, policy, ep.URL)
		resolved, resolveErr := p.resolvePage(ctx, frame, referer, 0)
		if resolveErr != nil {
			return
		}
		audio := strings.ToLower(strings.TrimSpace(option.Text()))
		for _, stream := range resolved {
			stream.Audio = audio
			streams = append(streams, stream)
		}
	})
	if len(streams) == 0 {
		return p.resolvePage(ctx, ep.URL, ep.URL, 0)
	}
	return streams, nil
}
func (p *OnlineCC) resolvePage(ctx context.Context, u, referer string, depth int) ([]domain.Stream, error) {
	return p.resolvePagePolicy(ctx, u, referer, depth, false)
}

// resolvePageWithBrowserOnFetchError is used by providers whose embedded player
// can reject the scraper's HTTP client while remaining available in a browser.
// The browser path remains bounded and rejects security challenge pages.
func (p *OnlineCC) resolvePageWithBrowserOnFetchError(ctx context.Context, u, referer string, depth int) ([]domain.Stream, error) {
	return p.resolvePagePolicy(ctx, u, referer, depth, true)
}

func (p *OnlineCC) resolvePagePolicy(ctx context.Context, u, referer string, depth int, browserOnFetchError bool) ([]domain.Stream, error) {
	if depth > 3 {
		return nil, fmt.Errorf("player externo não reconhecido")
	}
	if isAdvertisingURL(u) {
		return nil, fmt.Errorf("URL de anúncio ou rastreamento ignorada")
	}
	if parsed, err := url.Parse(u); err == nil && (parsed.Hostname() == "www.blogger.com" || parsed.Hostname() == "blogger.com") && parsed.Path == "/video.g" {
		streams, rpcErr := p.resolveBlogger(ctx, u)
		if rpcErr == nil && len(streams) > 0 {
			return streams, nil
		}
		// Some Blogger videos only publish their signed media URL after the
		// embedded player executes in a browser. Keep the RPC as the fast path,
		// then fall back to the same bounded DOM/JWPlayer extraction used for
		// other JavaScript-driven player pages.
		attempted := map[string]bool{u: true}
		if rendered, browserErr := p.resolveRenderedCandidates(ctx, u, depth, attempted, browserOnFetchError); browserErr == nil && len(rendered) > 0 {
			return rendered, nil
		} else if browserErr != nil {
			if rpcErr == nil {
				rpcErr = fmt.Errorf("RPC não retornou renditions")
			}
			return nil, fmt.Errorf("Blogger: %v; resolução pelo navegador: %w", rpcErr, browserErr)
		}
		if rpcErr != nil {
			return nil, rpcErr
		}
		return nil, fmt.Errorf("Blogger não publicou mídia no RPC nem no navegador")
	}
	r, e := p.Client.Do(ctx, "GET", u, nil, playerRequestHeaders(u, referer))
	if e != nil {
		if browserOnFetchError {
			attempted := map[string]bool{u: true}
			if streams, browserErr := p.resolveRenderedCandidates(ctx, u, depth, attempted, browserOnFetchError); browserErr == nil && len(streams) > 0 {
				return streams, nil
			} else if browserErr != nil {
				return nil, fmt.Errorf("requisição do player falhou (%v); resolução pelo navegador: %w", e, browserErr)
			}
		}
		return nil, e
	}
	defer r.Body.Close()
	b, e := io.ReadAll(io.LimitReader(r.Body, 8<<20))
	if e != nil {
		return nil, e
	}
	if securityChallenge(string(b)) {
		if browserOnFetchError {
			attempted := map[string]bool{u: true}
			if streams, browserErr := p.resolveRenderedCandidates(ctx, u, depth, attempted, browserOnFetchError); browserErr == nil && len(streams) > 0 {
				return streams, nil
			} else if browserErr != nil {
				return nil, fmt.Errorf("player HTTP permaneceu em verificação de segurança; resolução pelo navegador: %w", browserErr)
			}
		}
		return nil, fmt.Errorf("player permaneceu em verificação de segurança")
	}
	headers := anidriveMediaHeaders(u, referer)
	if strings.HasPrefix(strings.TrimSpace(string(b)), "#EXTM3U") {
		return []domain.Stream{{URL: u, Kind: "hls", Headers: headers}}, nil
	}
	if strings.HasPrefix(r.Header.Get("Content-Type"), "video/") {
		return []domain.Stream{{URL: u, Kind: "file", Headers: headers}}, nil
	}
	doc, e := goquery.NewDocumentFromReader(strings.NewReader(string(b)))
	if e != nil {
		return nil, e
	}
	candidates := pagePlayerCandidates(doc, u)
	var scripts []string
	doc.Find("script").Each(func(_ int, script *goquery.Selection) {
		scripts = append(scripts, script.Text())
	})
	for _, script := range scripts {
		for _, m := range jsMedia.FindAllStringSubmatch(script, -1) {
			if candidate := scrapedHTTPURL(u, m[1]); candidate != "" {
				if isStaticPlayerAsset(candidate) {
					continue
				}
				candidates = append(candidates, playerURLCandidate{URL: candidate})
			}
		}
	}
	candidates = uniquePlayerCandidates(candidates)
	var lastErr error
	attempted := map[string]bool{u: true}
	for _, candidate := range candidates {
		next := candidate.URL
		if next == u || attempted[next] || isAdvertisingURL(next) {
			continue
		}
		attempted[next] = true
		nextReferer := playerReferer(u, next, candidate.ReferrerPolicy, u)
		result, err := p.resolvePagePolicy(ctx, next, nextReferer, depth+1, browserOnFetchError)
		if err == nil && len(result) > 0 {
			return result, nil
		}
		lastErr = err
	}
	// Selenium in the legacy scraper reads iframe.src after scripts execute.
	// HTTP-only parsing cannot see iframes inserted later, so use a bounded
	// headless browser only after the static candidates fail.
	if streams, renderErr := p.resolveRenderedCandidates(ctx, u, depth, attempted, browserOnFetchError); renderErr == nil && len(streams) > 0 {
		return streams, nil
	} else if renderErr != nil && lastErr == nil {
		lastErr = renderErr
	}
	if lastErr != nil {
		return nil, fmt.Errorf("não foi possível abrir o reprodutor deste episódio: %w", lastErr)
	}
	return nil, fmt.Errorf("fonte não oferece um stream acessível para este episódio")
}

func (p *OnlineCC) resolveRenderedCandidates(ctx context.Context, pageURL string, depth int, attempted map[string]bool, browserOnFetchError bool) ([]domain.Stream, error) {
	rendered, err := renderedPlayerURLs(ctx, pageURL)
	if err != nil {
		return nil, err
	}
	var lastErr error
	for _, candidate := range rendered {
		next := scrapedHTTPURL(pageURL, candidate.URL)
		if next == "" || attempted[next] || isAdvertisingURL(next) {
			continue
		}
		attempted[next] = true
		nextReferer := playerReferer(pageURL, next, candidate.ReferrerPolicy, pageURL)
		streams, resolveErr := p.resolvePagePolicy(ctx, next, nextReferer, depth+1, browserOnFetchError)
		if resolveErr == nil && len(streams) > 0 {
			return streams, nil
		}
		lastErr = resolveErr
	}
	if lastErr != nil {
		return nil, lastErr
	}
	return nil, fmt.Errorf("player dinâmico não publicou uma URL de mídia")
}

func isStaticPlayerAsset(raw string) bool {
	parsed, err := url.Parse(raw)
	if err != nil {
		return true
	}
	switch strings.ToLower(path.Ext(parsed.Path)) {
	case ".js", ".css", ".gif", ".jpg", ".jpeg", ".png", ".webp", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot":
		return true
	default:
		return false
	}
}

const anidriveBrowserUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

// playerRequestHeaders reproduces the browser request metadata used when an
// episode embeds Anidrive. That host rejects the app's generic HTTP request
// with 403 even though the same token is served to an iframe from the episode.
func playerRequestHeaders(rawURL, referer string) map[string]string {
	headers := map[string]string{}
	if referer != "" {
		headers["Referer"] = referer
	}
	parsed, err := url.Parse(rawURL)
	if err != nil || !strings.EqualFold(parsed.Hostname(), "anidrive.click") {
		return headers
	}
	headers["User-Agent"] = anidriveBrowserUA
	headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
	headers["Sec-Fetch-Dest"] = "iframe"
	headers["Sec-Fetch-Mode"] = "navigate"
	headers["Sec-Fetch-Site"] = "cross-site"
	return headers
}

func isAnidriveURL(rawURL string) bool {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return false
	}
	host := strings.ToLower(parsed.Hostname())
	return host == "anidrive.click" || strings.HasSuffix(host, ".anidrive.click")
}

func anidriveMediaHeaders(rawURL, referer string) map[string]string {
	headers := map[string]string{}
	if referer != "" {
		headers["Referer"] = referer
	}
	if isAnidriveURL(rawURL) || isAnidriveURL(referer) {
		// The Anidrive media CDN expects the same browser identity that loaded
		// the iframe; otherwise validation and MPV can receive a 403.
		headers["User-Agent"] = anidriveBrowserUA
	}
	return headers
}
