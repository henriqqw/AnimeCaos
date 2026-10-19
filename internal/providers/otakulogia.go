package providers

import (
	"context"
	"encoding/json"
	"fmt"
	"net/url"
	"path"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
)

type Otakulogia struct {
	Client   *netx.Client
	Endpoint string
	Base     string
}

func NewOtakulogia(c *netx.Client) *Otakulogia {
	return &Otakulogia{Client: c, Endpoint: "https://api.otakulogia.com/graphql", Base: "https://otakulogia.com"}
}

func (p *Otakulogia) Name() string { return "otakulogia" }

type otakuGraphQLError struct {
	Message string `json:"message"`
}

type otakuGraphQLResponse[T any] struct {
	Data   T                   `json:"data"`
	Errors []otakuGraphQLError `json:"errors"`
}

func (p *Otakulogia) query(ctx context.Context, operation, query string, variables map[string]any, out any) error {
	request := map[string]any{"operationName": operation, "query": query, "variables": variables}
	if err := p.Client.JSON(ctx, "POST", p.Endpoint, request, map[string]string{"Content-Type": "application/json", "Referer": p.Base + "/"}, out); err != nil {
		return err
	}
	return nil
}

const otakuAnimeFields = `id upstreamCid name slug nameEn year status synopsis posterUrl audioMix hasNewEpisode`

const otakuSearchQuery = `query SearchAnimes($input: SearchAnimesInput) {
  searchAnimes(input: $input) {
    total offset limit
    items { ` + otakuAnimeFields + ` }
  }
}`

func (p *Otakulogia) Search(ctx context.Context, query string, page int) (domain.SearchResult, error) {
	out := domain.SearchResult{Items: []domain.Anime{}, Page: page, Warnings: []string{}}
	if page < 1 {
		page = 1
	}
	type result struct {
		Search struct {
			Total  int `json:"total"`
			Offset int `json:"offset"`
			Limit  int `json:"limit"`
			Items  []struct {
				UpstreamCID int    `json:"upstreamCid"`
				Name        string `json:"name"`
				Slug        string `json:"slug"`
				NameEN      string `json:"nameEn"`
				Synopsis    string `json:"synopsis"`
				PosterURL   string `json:"posterUrl"`
				Year        int    `json:"year"`
				Status      string `json:"status"`
				AudioMix    string `json:"audioMix"`
			} `json:"items"`
		} `json:"searchAnimes"`
	}
	var response otakuGraphQLResponse[result]
	if err := p.query(ctx, "SearchAnimes", otakuSearchQuery, map[string]any{"input": map[string]any{"query": strings.TrimSpace(query), "limit": 20, "offset": (page - 1) * 20}}, &response); err != nil {
		return out, err
	}
	if len(response.Errors) > 0 {
		return out, fmt.Errorf("busca Otakulogia: %s", response.Errors[0].Message)
	}
	for _, item := range response.Data.Search.Items {
		if item.UpstreamCID <= 0 || strings.TrimSpace(item.Name) == "" {
			continue
		}
		titles := []string{}
		if strings.TrimSpace(item.NameEN) != "" && normalized(item.NameEN) != normalized(item.Name) {
			titles = append(titles, item.NameEN)
		}
		anime := domain.Anime{ID: strconv.Itoa(item.UpstreamCID), Provider: p.Name(), Title: strings.TrimSpace(item.Name), Titles: titles, URL: strings.TrimRight(p.Base, "/") + "/" + strings.TrimLeft(item.Slug, "/"), Cover: item.PosterURL, Description: item.Synopsis, Status: item.Status, Audio: item.AudioMix, Season: 0}
		if item.Year > 0 {
			anime.Description = strings.TrimSpace(anime.Description)
		}
		out.Items = append(out.Items, anime)
	}
	limit := response.Data.Search.Limit
	if limit == 0 {
		limit = 20
	}
	out.HasNext = response.Data.Search.Total > response.Data.Search.Offset+limit
	return out, nil
}

var otakuSeasonNumberRE = regexp.MustCompile(`(?i)(?:temporada|season)\s*(\d+)`)
var otakuEpisodeNumberRE = regexp.MustCompile(`(?i)(?:\bT\s*\d+\s*)?(?:epis[oó]dio|episode|ep)\s*\.?\s*(\d+(?:\.\d+)?)`)
var otakuEpisodePrefixRE = regexp.MustCompile(`(?i)^\s*(?:T\s*\d+\s*)?(?:epis[oó]dio|episode|ep)\s*\.?\s*\d+(?:\.\d+)?\s*[-:–—.]?\s*`)

type otakuPlaybackVariant struct {
	UpstreamEpisodeID int    `json:"upstreamEpisodeId"`
	URL               string `json:"url"`
	Kind              string `json:"kind"`
	Audio             string `json:"audio"`
	Quality           string `json:"quality,omitempty"`
}

type otakuEpisodeGroup struct {
	episode  domain.Episode
	variants []otakuPlaybackVariant
}

const otakuDetailQuery = `query AnimeCatalogDetail($upstreamCid: Int!, $upstreamTid: Int) {
  animeCatalogDetail(upstreamCid: $upstreamCid, upstreamTid: $upstreamTid) {
    anime { upstreamCid name slug synopsis posterUrl audioMix }
    seasons { upstreamTid name audioType }
    episodes { id upstreamId title slug episodeNumber upstreamTempId videoUrl videoUrlFhd videoUrlSd videoType audioType }
  }
}`

func otakuSeasonNumber(name string) int {
	if match := otakuSeasonNumberRE.FindStringSubmatch(name); len(match) == 2 {
		value, _ := strconv.Atoi(match[1])
		return value
	}
	return 0
}

func otakuAudioLabel(value string) string {
	switch strings.ToUpper(strings.TrimSpace(value)) {
	case "DUB", "DUBLADO":
		return "dublado"
	case "LEG", "SUB", "LEGENDADO":
		return "legendado"
	default:
		return strings.ToLower(strings.TrimSpace(value))
	}
}

func (p *Otakulogia) Details(ctx context.Context, anime domain.Anime) (domain.Detail, error) {
	cid, err := strconv.Atoi(strings.TrimSpace(anime.ID))
	if err != nil || cid <= 0 {
		return domain.Detail{}, fmt.Errorf("identificador de anime Otakulogia inválido")
	}
	type result struct {
		Catalog struct {
			Anime struct {
				UpstreamCID int    `json:"upstreamCid"`
				Name        string `json:"name"`
				Slug        string `json:"slug"`
				Synopsis    string `json:"synopsis"`
				PosterURL   string `json:"posterUrl"`
				AudioMix    string `json:"audioMix"`
			} `json:"anime"`
			Seasons []struct {
				UpstreamTID int    `json:"upstreamTid"`
				Name        string `json:"name"`
				AudioType   string `json:"audioType"`
			} `json:"seasons"`
			Episodes []struct {
				ID             string  `json:"id"`
				UpstreamID     int     `json:"upstreamId"`
				Title          string  `json:"title"`
				Slug           string  `json:"slug"`
				EpisodeNumber  float64 `json:"episodeNumber"`
				UpstreamTempID int     `json:"upstreamTempId"`
				VideoURL       string  `json:"videoUrl"`
				VideoURLFHD    string  `json:"videoUrlFhd"`
				VideoURLSD     string  `json:"videoUrlSd"`
				VideoType      string  `json:"videoType"`
				AudioType      string  `json:"audioType"`
			} `json:"episodes"`
		} `json:"animeCatalogDetail"`
	}
	var response otakuGraphQLResponse[result]
	if err := p.query(ctx, "AnimeCatalogDetail", otakuDetailQuery, map[string]any{"upstreamCid": cid}, &response); err != nil {
		return domain.Detail{}, err
	}
	if len(response.Errors) > 0 {
		return domain.Detail{}, fmt.Errorf("detalhes Otakulogia: %s", response.Errors[0].Message)
	}
	catalog := response.Data.Catalog
	detail := domain.Detail{Anime: anime, Episodes: []domain.Episode{}}
	if catalog.Anime.Name != "" {
		detail.Anime.Title = catalog.Anime.Name
	}
	if catalog.Anime.Synopsis != "" {
		detail.Anime.Description = catalog.Anime.Synopsis
	}
	if catalog.Anime.PosterURL != "" {
		detail.Anime.Cover = catalog.Anime.PosterURL
	}
	if catalog.Anime.AudioMix != "" {
		detail.Anime.Audio = catalog.Anime.AudioMix
	}
	seasonNumbers := make(map[int]int, len(catalog.Seasons))
	for _, season := range catalog.Seasons {
		seasonNumbers[season.UpstreamTID] = otakuSeasonNumber(season.Name)
	}
	groups := map[string]*otakuEpisodeGroup{}
	for _, item := range catalog.Episodes {
		if item.UpstreamID <= 0 {
			continue
		}
		localNumber := item.EpisodeNumber
		if match := otakuEpisodeNumberRE.FindStringSubmatch(item.Title); len(match) == 2 {
			if parsed, parseErr := strconv.ParseFloat(match[1], 64); parseErr == nil {
				localNumber = parsed
			}
		}
		seasonNumber := seasonNumbers[item.UpstreamTempID]
		title := strings.TrimSpace(otakuEpisodePrefixRE.ReplaceAllString(item.Title, ""))
		if title == "" {
			title = strings.TrimSpace(item.Title)
		}
		key := fmt.Sprintf("%d/%g", seasonNumber, localNumber)
		if localNumber <= 0 {
			key += "/" + normalized(title)
		}
		group := groups[key]
		if group == nil {
			group = &otakuEpisodeGroup{episode: domain.Episode{AnimeID: anime.ID, Provider: p.Name(), Title: title, Number: localNumber, Season: seasonNumber}}
			group.episode.ID = fmt.Sprintf("%d:%d:%g:%s", cid, seasonNumber, localNumber, normalized(title))
			groups[key] = group
		}
		for _, candidate := range []struct{ raw, quality string }{{item.VideoURLFHD, "1080p"}, {item.VideoURL, ""}, {item.VideoURLSD, "480p"}} {
			if candidate.raw == "" {
				continue
			}
			parsed, parseErr := url.Parse(candidate.raw)
			if parseErr != nil || (parsed.Scheme != "http" && parsed.Scheme != "https") || parsed.Host == "" {
				continue
			}
			kind := "file"
			if strings.EqualFold(path.Ext(parsed.Path), ".m3u8") || strings.EqualFold(item.VideoType, "hls") {
				kind = "hls"
			}
			variant := otakuPlaybackVariant{UpstreamEpisodeID: item.UpstreamID, URL: parsed.String(), Kind: kind, Audio: otakuAudioLabel(item.AudioType), Quality: candidate.quality}
			duplicate := false
			for _, current := range group.variants {
				if current.UpstreamEpisodeID == variant.UpstreamEpisodeID && current.URL == variant.URL {
					duplicate = true
					break
				}
			}
			if !duplicate {
				group.variants = append(group.variants, variant)
			}
		}
	}
	for _, group := range groups {
		if len(group.variants) == 0 {
			continue
		}
		payload, err := json.Marshal(group.variants)
		if err != nil {
			return domain.Detail{}, err
		}
		group.episode.URL = string(payload)
		seenAudio := map[string]bool{}
		for _, variant := range group.variants {
			if variant.Audio != "" && !seenAudio[variant.Audio] {
				seenAudio[variant.Audio] = true
				if group.episode.Audio != "" {
					group.episode.Audio += " & "
				}
				group.episode.Audio += variant.Audio
			}
		}
		detail.Episodes = append(detail.Episodes, group.episode)
	}
	sort.SliceStable(detail.Episodes, func(i, j int) bool {
		if detail.Episodes[i].Season != detail.Episodes[j].Season {
			if detail.Episodes[i].Season == 0 {
				return false
			}
			if detail.Episodes[j].Season == 0 {
				return true
			}
			return detail.Episodes[i].Season < detail.Episodes[j].Season
		}
		if detail.Episodes[i].Number != detail.Episodes[j].Number {
			if detail.Episodes[i].Number == 0 {
				return false
			}
			if detail.Episodes[j].Number == 0 {
				return true
			}
			return detail.Episodes[i].Number < detail.Episodes[j].Number
		}
		return normalized(detail.Episodes[i].Title) < normalized(detail.Episodes[j].Title)
	})
	if len(detail.Episodes) == 0 {
		return detail, fmt.Errorf("nenhum episódio reproduzível encontrado nesta fonte")
	}
	detail.Anime.EpisodeCount = len(detail.Episodes)
	return detail, nil
}

const otakuWatchGateQuery = `query WatchPlayGate($upstreamEpisodeId: Int) {
  requiresVipToWatch(upstreamEpisodeId: $upstreamEpisodeId)
}`

func (p *Otakulogia) Resolve(ctx context.Context, episode domain.Episode) ([]domain.Stream, error) {
	var variants []otakuPlaybackVariant
	if err := json.Unmarshal([]byte(episode.URL), &variants); err != nil {
		return nil, fmt.Errorf("dados de reprodução Otakulogia inválidos: %w", err)
	}
	streams := make([]domain.Stream, 0, len(variants))
	seen := map[string]bool{}
	var lastErr error
	for _, variant := range variants {
		if err := ctx.Err(); err != nil {
			return streams, err
		}
		if variant.UpstreamEpisodeID <= 0 || variant.URL == "" || seen[variant.URL] {
			continue
		}
		type gateData struct {
			RequiresVIP bool `json:"requiresVipToWatch"`
		}
		var gate otakuGraphQLResponse[gateData]
		if err := p.query(ctx, "WatchPlayGate", otakuWatchGateQuery, map[string]any{"upstreamEpisodeId": variant.UpstreamEpisodeID}, &gate); err != nil {
			lastErr = err
			continue
		}
		if len(gate.Errors) > 0 {
			lastErr = fmt.Errorf("checagem de acesso Otakulogia: %s", gate.Errors[0].Message)
			continue
		}
		if gate.Data.RequiresVIP {
			lastErr = fmt.Errorf("este episódio exige acesso VIP na Otakulogia")
			continue
		}
		seen[variant.URL] = true
		stream := domain.Stream{URL: variant.URL, Kind: variant.Kind, Audio: variant.Audio}
		if variant.Quality != "" {
			stream.Qualities = []string{variant.Quality}
		}
		streams = append(streams, stream)
	}
	if len(streams) > 0 {
		return streams, nil
	}
	if lastErr != nil {
		return nil, lastErr
	}
	return nil, fmt.Errorf("Otakulogia não oferece stream acessível para este episódio")
}
