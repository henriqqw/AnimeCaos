package providers

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
)

type AnimesFHD struct {
	Client *netx.Client
	Base   string
}

var _ domain.AnimeProvider = (*AnimesFHD)(nil)

func NewAnimesFHD(c *netx.Client) *AnimesFHD { return &AnimesFHD{c, "https://animesfhd.net"} }
func (p *AnimesFHD) Name() string            { return "animesfhd" }

func fhdHeaders() map[string]string {
	return map[string]string{
		"Referer":    "https://animesfhd.net/",
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
	}
}

type fhdSeries struct {
	ID           json.Number `json:"id"`
	Title        string      `json:"title"`
	AltTitles    string      `json:"alt_titles"`
	Description  string      `json:"description"`
	Cover        string      `json:"cover_image"`
	Banner       string      `json:"backdrop_image"`
	Status       string      `json:"status"`
	Category     string      `json:"category"`
	Audios       []string    `json:"audios"`
	Year         int         `json:"year"`
	EpisodeCount int         `json:"episode_count"`
}

func fhdValidID(id string) bool {
	n, err := strconv.ParseInt(id, 10, 64)
	return err == nil && n > 0 && strconv.FormatInt(n, 10) == id
}

func (p *AnimesFHD) absolute(raw string) string {
	base, err := url.Parse(p.Base + "/")
	if err != nil || strings.TrimSpace(raw) == "" {
		return ""
	}
	u, err := url.Parse(strings.TrimSpace(raw))
	if err != nil {
		return ""
	}
	u = base.ResolveReference(u)
	if (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" || u.User != nil || netx.IsAdvertisingURL(u.String()) {
		return ""
	}
	return u.String()
}

func fhdAudio(values ...string) string {
	out := []string{}
	seen := map[string]bool{}
	for _, value := range values {
		value = strings.ToLower(strings.TrimSpace(value))
		if (value == "legendado" || value == "dublado") && !seen[value] {
			seen[value] = true
			out = append(out, value)
		}
	}
	return strings.Join(out, " & ")
}

func (p *AnimesFHD) model(a fhdSeries) domain.Anime {
	titles := []string{}
	seen := map[string]bool{}
	for _, title := range append([]string{a.Title}, strings.Split(a.AltTitles, "\n")...) {
		title = strings.TrimSpace(title)
		if title != "" && !seen[title] {
			seen[title] = true
			titles = append(titles, title)
		}
	}
	audio := fhdAudio(a.Audios...)
	if audio == "" {
		audio = fhdAudio(a.Category)
	}
	format := ""
	if a.Category == "filme" {
		format = "movie"
	}
	return domain.Anime{ID: a.ID.String(), Provider: p.Name(), Title: strings.TrimSpace(a.Title), Titles: titles,
		URL: p.absolute("/serie/" + a.ID.String()), Cover: p.absolute(a.Cover), Banner: p.absolute(a.Banner),
		Description: a.Description, Status: a.Status, Audio: audio, Year: a.Year, Format: format, EpisodeCount: a.EpisodeCount}
}

func (p *AnimesFHD) Search(ctx context.Context, q string, page int) (domain.SearchResult, error) {
	page = max(1, page)
	out := domain.SearchResult{Items: []domain.Anime{}, Page: page, Warnings: []string{}}
	params := url.Values{"pagination": {"1"}, "page": {strconv.Itoa(page)}, "per_page": {"24"}}
	if q = strings.TrimSpace(q); q != "" {
		params.Set("q", q)
	} else {
		params.Set("sort", "popular")
	}
	var response struct {
		Series  []fhdSeries `json:"series"`
		HasMore bool        `json:"has_more"`
	}
	if err := p.Client.JSON(ctx, http.MethodGet, p.Base+"/api/series?"+params.Encode(), nil, fhdHeaders(), &response); err != nil {
		return out, err
	}
	if response.Series == nil {
		return out, fmt.Errorf("AnimesFHD: resposta sem catálogo")
	}
	seen := map[string]bool{}
	for _, item := range response.Series {
		id := item.ID.String()
		if fhdValidID(id) && strings.TrimSpace(item.Title) != "" && !seen[id] {
			seen[id] = true
			out.Items = append(out.Items, p.model(item))
		}
	}
	out.HasNext = response.HasMore
	return out, nil
}

type fhdVersion struct {
	SeriesID  json.Number   `json:"series_id"`
	SeriesIDs []json.Number `json:"series_ids"`
	EpisodeID json.Number   `json:"episode_id"`
	Season    int           `json:"season"`
	Part      int           `json:"part"`
	Audio     string        `json:"audio"`
}

func (v fhdVersion) contains(id string) bool {
	if v.SeriesID.String() == id {
		return true
	}
	for _, copyID := range v.SeriesIDs {
		if copyID.String() == id {
			return true
		}
	}
	return false
}

type fhdDetails struct {
	Series   fhdSeries    `json:"series"`
	Versions []fhdVersion `json:"versions"`
	SEO      struct {
		Season int    `json:"season"`
		Format string `json:"format"`
	} `json:"seo"`
	MAL struct {
		ID int `json:"id"`
	} `json:"mal"`
	Episodes []struct {
		ID     json.Number `json:"id"`
		Number float64     `json:"episode_number"`
		Title  string      `json:"title"`
	} `json:"episodes"`
	HasMore bool `json:"has_more"`
}

func (p *AnimesFHD) detailsPage(ctx context.Context, id string, page int) (fhdDetails, error) {
	var response fhdDetails
	err := p.Client.JSON(ctx, http.MethodGet, p.Base+"/api/series/"+id+"?page="+strconv.Itoa(page)+"&per_page=200", nil, fhdHeaders(), &response)
	if err == nil && (response.Series.ID.String() != id || strings.TrimSpace(response.Series.Title) == "") {
		err = fmt.Errorf("AnimesFHD: identidade da obra não confirmada")
	}
	return response, err
}

func (p *AnimesFHD) Details(ctx context.Context, anime domain.Anime) (domain.Detail, error) {
	if !fhdValidID(anime.ID) {
		return domain.Detail{}, fmt.Errorf("AnimesFHD: identificador de obra inválido")
	}
	first, err := p.detailsPage(ctx, anime.ID, 1)
	if err != nil {
		return domain.Detail{}, err
	}
	out := domain.Detail{Anime: p.model(first.Series), Episodes: []domain.Episode{}}
	out.Anime.MALID = first.MAL.ID
	out.Anime.Season = first.SEO.Season
	if first.SEO.Format != "" {
		out.Anime.Format = first.SEO.Format
	}
	ids := []string{anime.ID}
	versions := map[string]fhdVersion{}
	queued := map[string]bool{anime.ID: true}
	// Only the selected work's explicit versions are followed, never related
	// titles or versions recursively discovered on subsequent pages.
	for _, version := range first.Versions {
		id := version.SeriesID.String()
		if !fhdValidID(id) {
			continue
		}
		// The API already merges series_ids into the representative's list.
		if version.contains(anime.ID) {
			id = anime.ID
		}
		if previous, ok := versions[id]; ok && (previous.Season != version.Season || previous.Part != version.Part || previous.Audio != version.Audio) {
			return domain.Detail{}, fmt.Errorf("AnimesFHD: versão com temporada ou áudio ambíguos")
		}
		versions[id] = version
		if !queued[id] {
			queued[id] = true
			ids = append(ids, id)
		}
	}
	if len(ids) > 100 {
		return domain.Detail{}, fmt.Errorf("AnimesFHD: limite de versões excedido")
	}
	seen := map[string]bool{}
	type slot struct{ index, part int }
	slots := map[string]slot{}
	for _, id := range ids {
		page := first
		if id != anime.ID {
			page, err = p.detailsPage(ctx, id, 1)
			if err != nil {
				return domain.Detail{}, err
			}
		}
		season, part, audio := page.SEO.Season, 0, fhdAudio(page.Series.Category)
		if version, ok := versions[id]; ok {
			season = version.Season
			part = version.Part
			if version.Audio != "" {
				audio = fhdAudio(version.Audio)
			}
		}
		if id == anime.ID {
			out.Anime.Season = season
		}
		pageSeen := map[string]bool{}
		for n := 1; ; n++ {
			added := 0
			for _, ep := range page.Episodes {
				episodeID := ep.ID.String()
				if !fhdValidID(episodeID) || pageSeen[episodeID] {
					continue
				}
				pageSeen[episodeID] = true
				added++
				if seen[episodeID] {
					continue
				}
				seen[episodeID] = true
				// Only an explicit season and number can join audio variants.
				// Resolve obtains their episode IDs from the API at playback time.
				if season > 0 && ep.Number > 0 {
					key := strconv.Itoa(season) + ":" + strconv.FormatFloat(ep.Number, 'f', -1, 64)
					if previous, ok := slots[key]; ok {
						if previous.part != part {
							return domain.Detail{}, fmt.Errorf("AnimesFHD: partes com numeração sobreposta não são suportadas")
						}
						item := &out.Episodes[previous.index]
						item.Audio = fhdAudio(append(strings.Split(item.Audio, " & "), audio)...)
						continue
					}
					slots[key] = slot{index: len(out.Episodes), part: part}
				}
				out.Episodes = append(out.Episodes, domain.Episode{ID: episodeID, AnimeID: id, Provider: p.Name(),
					Title: ep.Title, Number: ep.Number, Season: season, Audio: audio, URL: p.absolute("/episod/" + episodeID)})
			}
			if !page.HasMore {
				break
			}
			if added == 0 || n >= 20 {
				return domain.Detail{}, fmt.Errorf("AnimesFHD: paginação de episódios incompleta")
			}
			page, err = p.detailsPage(ctx, id, n+1)
			if err != nil {
				return domain.Detail{}, err
			}
		}
	}
	sort.SliceStable(out.Episodes, func(i, j int) bool {
		a, b := out.Episodes[i], out.Episodes[j]
		if a.Season != b.Season {
			return a.Season < b.Season
		}
		return a.Number < b.Number
	})
	out.Anime.EpisodeCount = len(out.Episodes)
	return out, nil
}

type fhdEpisode struct {
	Episode struct {
		ID       json.Number `json:"id"`
		SeriesID json.Number `json:"series_id"`
		Number   *float64    `json:"episode_number"`
	} `json:"episode"`
	Versions []fhdVersion `json:"versions"`
	Sources  []struct {
		URL         string `json:"url"`
		Kind        string `json:"kind"`
		MediaKind   string `json:"media_kind"`
		Audio       string `json:"audio"`
		NativeVideo bool   `json:"native_video"`
	} `json:"sources"`
}

func (p *AnimesFHD) episode(ctx context.Context, id string) (fhdEpisode, error) {
	var response fhdEpisode
	err := p.Client.JSON(ctx, http.MethodGet, p.Base+"/api/episodes/"+id, nil, fhdHeaders(), &response)
	if err == nil && (response.Episode.ID.String() != id || !fhdValidID(response.Episode.SeriesID.String())) {
		err = fmt.Errorf("AnimesFHD: identidade do episódio não confirmada")
	}
	return response, err
}

func (p *AnimesFHD) Resolve(ctx context.Context, ep domain.Episode) ([]domain.Stream, error) {
	if !fhdValidID(ep.ID) {
		return nil, fmt.Errorf("AnimesFHD: identificador de episódio inválido")
	}
	response, err := p.episode(ctx, ep.ID)
	if err != nil {
		return nil, err
	}
	owner := response.Episode.SeriesID.String()
	validOwner := ep.AnimeID == "" || owner == ep.AnimeID
	var own fhdVersion
	for _, version := range response.Versions {
		if version.contains(owner) {
			own = version
			validOwner = validOwner || version.contains(ep.AnimeID)
		}
	}
	if !validOwner || (ep.Number > 0 && response.Episode.Number != nil && ep.Number != *response.Episode.Number) {
		return nil, fmt.Errorf("AnimesFHD: identidade do episódio não confirmada")
	}
	pages := []fhdEpisode{response}
	audios := []string{fhdAudio(own.Audio)}
	if audios[0] == "" {
		audios[0] = fhdAudio(ep.Audio)
	}
	var lastErr error
	visited := map[string]bool{ep.ID: true}
	// episode_id is supplied for the same explicit episode number by the API.
	// Match season/part too; a sequel's E1 is never an alternate audio of E1.
	for _, version := range response.Versions {
		id := version.EpisodeID.String()
		if own.Season <= 0 || response.Episode.Number == nil || version.Season != own.Season || version.Part != own.Part || !fhdValidID(id) || visited[id] {
			continue
		}
		visited[id] = true
		alternate, err := p.episode(ctx, id)
		if err != nil {
			if ctx.Err() != nil {
				return nil, ctx.Err()
			}
			lastErr = err
			continue
		}
		if !version.contains(alternate.Episode.SeriesID.String()) || alternate.Episode.Number == nil || *alternate.Episode.Number != *response.Episode.Number {
			lastErr = fmt.Errorf("AnimesFHD: identidade do áudio alternativo não confirmada")
			continue
		}
		pages = append(pages, alternate)
		audios = append(audios, fhdAudio(version.Audio))
	}
	out := []domain.Stream{}
	seen := map[string]bool{}
	for i, page := range pages {
		for _, source := range page.Sources {
			if !source.NativeVideo || strings.EqualFold(strings.TrimSpace(source.Kind), "embed") {
				continue
			}
			raw := p.absolute(source.URL)
			audio := fhdAudio(source.Audio)
			if audio == "" {
				audio = audios[i]
			}
			key := raw + "\n" + audio
			if raw == "" || seen[key] {
				continue
			}
			seen[key] = true
			u, _ := url.Parse(raw)
			kind := "hls"
			if source.MediaKind != "s6" && !strings.EqualFold(source.Kind, "hls") && !strings.HasSuffix(strings.ToLower(u.Path), ".m3u8") && !strings.HasSuffix(strings.ToLower(u.Query().Get("playlist")), ".m3u8") {
				var err error
				kind, err = p.mediaKind(ctx, raw)
				if err != nil {
					if ctx.Err() != nil {
						return nil, ctx.Err()
					}
					lastErr = err
					continue
				}
			}
			out = append(out, domain.Stream{URL: raw, Kind: kind, Audio: audio, Headers: fhdHeaders()})
		}
	}
	if len(out) == 0 {
		if lastErr != nil {
			return nil, lastErr
		}
		return nil, fmt.Errorf("este episódio está indisponível no AnimesFHD")
	}
	return out, nil
}

// Opaque public resolvers can redirect to either MP4 or HLS. Inspect only a
// small prefix and retain the public resolver, not the expiring redirect URL.
func (p *AnimesFHD) mediaKind(ctx context.Context, raw string) (string, error) {
	headers := fhdHeaders()
	headers["Range"] = "bytes=0-511"
	response, err := p.Client.Do(ctx, http.MethodGet, raw, nil, headers)
	if err != nil {
		return "", err
	}
	defer response.Body.Close()
	prefix, err := io.ReadAll(io.LimitReader(response.Body, 512))
	if err != nil {
		return "", err
	}
	if strings.HasPrefix(strings.TrimSpace(string(prefix)), "#EXTM3U") {
		return "hls", nil
	}
	contentType := strings.ToLower(response.Header.Get("Content-Type"))
	if len(prefix) > 0 && (strings.HasPrefix(contentType, "video/") || (len(prefix) >= 8 && string(prefix[4:8]) == "ftyp")) {
		return "file", nil
	}
	return "", fmt.Errorf("AnimesFHD: a origem não retornou vídeo nativo")
}
