package providers

import (
	"context"
	"fmt"
	"html"
	"io"
	"net/url"
	"path"
	"regexp"
	"strconv"
	"strings"

	"github.com/PuerkitoBio/goquery"
	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
)

type SushiAnimes struct {
	Client *netx.Client
	Base   string
}

func NewSushiAnimes(c *netx.Client) *SushiAnimes {
	return &SushiAnimes{Client: c, Base: "https://sushianimes.com.br"}
}

func (p *SushiAnimes) Name() string { return "sushianimes" }

func (p *SushiAnimes) document(ctx context.Context, rawURL string) (*goquery.Document, error) {
	r, err := p.Client.Do(ctx, "GET", rawURL, nil, nil)
	if err != nil {
		return nil, err
	}
	defer r.Body.Close()
	return goquery.NewDocumentFromReader(io.LimitReader(r.Body, 12<<20))
}

func (p *SushiAnimes) Search(ctx context.Context, query string, page int) (domain.SearchResult, error) {
	out := domain.SearchResult{Items: []domain.Anime{}, Page: page, Warnings: []string{}}
	query = strings.TrimSpace(query)
	if query == "" {
		return out, nil
	}
	searchURL := strings.TrimRight(p.Base, "/") + "/search/" + url.PathEscape(query)
	if page > 1 {
		searchURL += "/" + strconv.Itoa(page)
	}
	doc, err := p.document(ctx, searchURL)
	if err != nil {
		return out, err
	}
	baseURL, _ := url.Parse(p.Base)
	seen := map[string]bool{}
	appendAnime := func(link *goquery.Selection) {
		href, _ := link.Attr("href")
		href = absolute(p.Base, href)
		rawTitle := strings.TrimSpace(link.Text())
		title, audio, aliases := sushiCatalogTitle(rawTitle)
		if title == "" || href == "" || seen[href] {
			return
		}
		parsed, err := url.Parse(href)
		if err != nil || baseURL == nil || !strings.EqualFold(parsed.Hostname(), baseURL.Hostname()) {
			return
		}
		seen[href] = true
		cover, _ := link.Closest(".list-item, .list-movie, article, .item").Find("img").First().Attr("data-src")
		if cover == "" {
			cover, _ = link.Closest(".list-item, .list-movie, article, .item").Find("img").First().Attr("src")
		}
		coverURL := ""
		if cover != "" {
			coverURL = absolute(p.Base, cover)
		}
		out.Items = append(out.Items, domain.Anime{ID: href, Provider: p.Name(), Title: title, Titles: aliases, URL: href, Cover: coverURL, Audio: audio})
	}
	doc.Find("a.list-title[href], .list-caption a[href*='/anime/']").Each(func(_ int, link *goquery.Selection) {
		appendAnime(link)
	})
	if len(out.Items) == 0 {
		doc.Find("a[href*='/anime/']").Each(func(_ int, link *goquery.Selection) { appendAnime(link) })
	}
	out.HasNext = doc.Find(".pagination a.next, a[rel='next'], .page-item.next a").Length() > 0
	return out, nil
}

var sushiEpisodePathRE = regexp.MustCompile(`-(\d+)-season-(\d+(?:\.\d+)?)-episode/?$`)
var sushiSeasonRE = regexp.MustCompile(`(?i)(?:temporada|season)\s*(\d+)|(\d+)\s*(?:[º°]\s*)?(?:temporada|season)`)
var sushiEpisodeLabelRE = regexp.MustCompile(`(?i)continuar\s*|\d+\s*[º°.]?\s*epis[oó]dio\s*`)
var sushiEmbedURLRE = regexp.MustCompile(`(?i)playerEmbed\s*=\s*["']((?:https?:)?//[^"']+|https?://[^"']+)["']`)
var sushiAudioSuffixRE = regexp.MustCompile(`(?i)\s*[\[(]\s*(dublado|legendado|dub|sub)\s*[\])]\s*$`)

func sushiCatalogTitle(raw string) (string, string, []string) {
	raw = strings.TrimSpace(raw)
	title := strings.TrimSpace(sushiAudioSuffixRE.ReplaceAllString(raw, ""))
	if title == raw {
		return title, "", nil
	}
	audioMatch := sushiAudioSuffixRE.FindStringSubmatch(raw)
	audio := ""
	if len(audioMatch) == 2 {
		switch strings.ToLower(audioMatch[1]) {
		case "dublado", "dub":
			audio = "dublado"
		case "legendado", "sub":
			audio = "legendado"
		}
	}
	return title, audio, []string{raw}
}

func sushiSeasonNumber(label string) int {
	match := sushiSeasonRE.FindStringSubmatch(label)
	if len(match) != 3 {
		return 0
	}
	value := match[1]
	if value == "" {
		value = match[2]
	}
	season, _ := strconv.Atoi(value)
	return season
}

func (p *SushiAnimes) Details(ctx context.Context, anime domain.Anime) (domain.Detail, error) {
	doc, err := p.document(ctx, anime.URL)
	if err != nil {
		return domain.Detail{}, err
	}
	detail := domain.Detail{Anime: anime, Episodes: []domain.Episode{}}
	baseURL, _ := url.Parse(p.Base)
	if rawTitle := strings.TrimSpace(doc.Find("h1").First().Text()); rawTitle != "" {
		title, audio, aliases := sushiCatalogTitle(rawTitle)
		detail.Anime.Title = title
		detail.Anime.Titles = append(detail.Anime.Titles, aliases...)
		if detail.Anime.Audio == "" {
			detail.Anime.Audio = audio
		}
	}
	if detail.Anime.Cover == "" {
		cover, _ := doc.Find(".detail-poster img, .anime-poster img, .poster img").First().Attr("src")
		if cover == "" {
			cover, _ = doc.Find(".detail-poster img, .anime-poster img, .poster img").First().Attr("data-src")
		}
		if cover != "" {
			detail.Anime.Cover = absolute(p.Base, cover)
		}
	}
	doc.Find("a.epx-card[href]").Each(func(_ int, link *goquery.Selection) {
		href, _ := link.Attr("href")
		href = absolute(anime.URL, href)
		parsed, parseErr := url.Parse(href)
		if parseErr != nil || baseURL == nil || !strings.EqualFold(parsed.Hostname(), baseURL.Hostname()) {
			return
		}
		match := sushiEpisodePathRE.FindStringSubmatch(parsed.Path)
		if len(match) != 3 {
			return
		}
		number, _ := strconv.ParseFloat(match[2], 64)
		title, _ := link.Find(".epx-title, .episode-title, .title").First().Attr("title")
		if title == "" {
			title = strings.TrimSpace(sushiEpisodeLabelRE.ReplaceAllString(link.Text(), ""))
		}
		season := 0
		if paneID, ok := link.Closest(".tab-pane").Attr("id"); ok && paneID != "" {
			doc.Find("a[href], button[data-bs-target], [data-target]").EachWithBreak(func(_ int, tab *goquery.Selection) bool {
				target, _ := tab.Attr("href")
				if target == "" {
					target, _ = tab.Attr("data-bs-target")
				}
				if target == "" {
					target, _ = tab.Attr("data-target")
				}
				if target == "#"+paneID {
					season = sushiSeasonNumber(strings.TrimSpace(tab.Text()))
					return false
				}
				return true
			})
		}
		id := parsed.Path
		detail.Episodes = append(detail.Episodes, domain.Episode{ID: id, URL: href, AnimeID: anime.ID, Provider: p.Name(), Title: title, Number: number, Season: season, Audio: detail.Anime.Audio})
	})
	if len(detail.Episodes) == 0 {
		return detail, fmt.Errorf("nenhum episódio encontrado nesta fonte")
	}
	detail.Anime.EpisodeCount = len(detail.Episodes)
	return detail, nil
}

func (p *SushiAnimes) Resolve(ctx context.Context, episode domain.Episode) ([]domain.Stream, error) {
	doc, err := p.document(ctx, episode.URL)
	if err != nil {
		return nil, err
	}
	buttons := doc.Find(".btn-service[data-embed], .btn-service[data-id], .play-btn[data-embed], .play-btn[data-id]")
	if buttons.Length() == 0 {
		streams, fallbackErr := p.resolveEmbeddedPage(ctx, episode.URL)
		if fallbackErr == nil && len(streams) > 0 {
			return applySushiAudio(streams, episode.Audio), nil
		}
		if fallbackErr != nil {
			return nil, fmt.Errorf("player Sushi sem opção AJAX; extração do player incorporado: %w", fallbackErr)
		}
		return nil, fmt.Errorf("player Sushi sem opção AJAX nem stream incorporado")
	}
	ordered := make([]*goquery.Selection, 0, buttons.Length())
	buttons.Each(func(_ int, button *goquery.Selection) {
		class, _ := button.Attr("class")
		if _, selected := button.Attr("selected"); selected || strings.Contains(" "+class+" ", " selected ") {
			ordered = append([]*goquery.Selection{button}, ordered...)
		} else {
			ordered = append(ordered, button)
		}
	})
	streams := []domain.Stream{}
	seen := map[string]bool{}
	var lastErr error
	for _, button := range ordered {
		if err := ctx.Err(); err != nil {
			return streams, err
		}
		id, _ := button.Attr("data-embed")
		if id == "" {
			id, _ = button.Attr("data-id")
		}
		if id == "" {
			continue
		}
		form := url.Values{"id": {id}}
		if token, ok := doc.Find("input[name='_TOKEN']").First().Attr("value"); ok {
			form.Set("_TOKEN", token)
		}
		endpoint := strings.TrimRight(p.Base, "/") + "/ajax/embed"
		r, requestErr := p.Client.Do(ctx, "POST", endpoint, []byte(form.Encode()), map[string]string{
			"Content-Type":     "application/x-www-form-urlencoded; charset=UTF-8",
			"X-Requested-With": "XMLHttpRequest",
			"Referer":          episode.URL,
			"Origin":           p.Base,
		})
		if requestErr != nil {
			lastErr = requestErr
			continue
		}
		body, readErr := io.ReadAll(io.LimitReader(r.Body, 2<<20))
		r.Body.Close()
		if readErr != nil {
			lastErr = readErr
			continue
		}
		doc, parseErr := goquery.NewDocumentFromReader(strings.NewReader(string(body)))
		if parseErr != nil {
			lastErr = parseErr
			continue
		}
		srcdoc, _ := doc.Find("iframe[srcdoc]").First().Attr("srcdoc")
		srcdoc = html.UnescapeString(srcdoc)
		match := sushiEmbedURLRE.FindStringSubmatch(srcdoc)
		if len(match) != 2 {
			lastErr = fmt.Errorf("player Sushi não retornou URL de mídia")
			continue
		}
		mediaURL := scrapedHTTPURL(episode.URL, match[1])
		if mediaURL == "" || seen[mediaURL] {
			continue
		}
		seen[mediaURL] = true
		kind := "file"
		if parsed, parseErr := url.Parse(mediaURL); parseErr == nil && strings.EqualFold(path.Ext(parsed.Path), ".m3u8") {
			kind = "hls"
		}
		label, _ := button.Attr("data-player-name")
		label = strings.ToLower(strings.TrimSpace(label))
		if label != "dublado" && label != "legendado" && label != "dub" && label != "sub" {
			label = episode.Audio
		}
		streams = append(streams, domain.Stream{URL: mediaURL, Kind: kind, Audio: strings.ToLower(label), Headers: map[string]string{"Referer": episode.URL}})
	}
	if len(streams) > 0 {
		return streams, nil
	}
	if fallback, fallbackErr := p.resolveEmbeddedPage(ctx, episode.URL); fallbackErr == nil && len(fallback) > 0 {
		return applySushiAudio(fallback, episode.Audio), nil
	} else if fallbackErr != nil {
		if lastErr == nil {
			lastErr = fallbackErr
		} else {
			lastErr = fmt.Errorf("%v; extração do player incorporado: %w", lastErr, fallbackErr)
		}
	}
	if lastErr != nil {
		return nil, lastErr
	}
	return nil, fmt.Errorf("fonte Sushi não oferece stream acessível para este episódio")
}

func (p *SushiAnimes) resolveEmbeddedPage(ctx context.Context, episodeURL string) ([]domain.Stream, error) {
	// Sushi pages usually return the embed id through /ajax/embed. Some pages
	// omit that control or expose the player directly, so use the shared,
	// advertisement-filtered player extractor as a bounded fallback.
	resolver := &OnlineCC{Client: p.Client, Base: p.Base}
	return resolver.resolvePage(ctx, episodeURL, episodeURL, 0)
}

func applySushiAudio(streams []domain.Stream, audio string) []domain.Stream {
	for i := range streams {
		if strings.TrimSpace(streams[i].Audio) == "" {
			streams[i].Audio = strings.ToLower(strings.TrimSpace(audio))
		}
	}
	return streams
}
