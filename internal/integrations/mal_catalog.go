package integrations

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/store"
)

const malDiscoveryFields = "id,title,main_picture,alternative_titles,media_type,num_episodes,mean,start_date,synopsis"

type MALCatalog struct {
	Client   *netx.Client
	Store    *store.Store
	URL      string
	ClientID string
	Gate     *netx.Gate
}

func NewMALCatalog(client *netx.Client, db *store.Store) *MALCatalog {
	return &MALCatalog{
		Client:   client,
		Store:    db,
		URL:      defaultMALAPIBase,
		ClientID: MALClientID,
		Gate:     &netx.Gate{Interval: time.Second},
	}
}

type malCatalogAnime struct {
	ID      int    `json:"id"`
	Title   string `json:"title"`
	Picture struct {
		Medium string `json:"medium"`
		Large  string `json:"large"`
	} `json:"main_picture"`
	AlternativeTitles struct {
		English  string   `json:"en"`
		Japanese string   `json:"ja"`
		Synonyms []string `json:"synonyms"`
	} `json:"alternative_titles"`
	MediaType string  `json:"media_type"`
	Episodes  int     `json:"num_episodes"`
	Score     float64 `json:"mean"`
	StartDate string  `json:"start_date"`
	Synopsis  string  `json:"synopsis"`
}

func (a malCatalogAnime) model() domain.Anime {
	primary := uniqueTitles(a.Title, a.AlternativeTitles.English, a.AlternativeTitles.Japanese)
	titles := uniqueTitles(append(append([]string{}, primary...), a.AlternativeTitles.Synonyms...)...)
	cover := a.Picture.Large
	if cover == "" {
		cover = a.Picture.Medium
	}
	year := 0
	if len(a.StartDate) >= 4 {
		year, _ = strconv.Atoi(a.StartDate[:4])
	}
	return domain.Anime{
		ID:            strconv.Itoa(a.ID),
		Provider:      "myanimelist",
		Title:         a.Title,
		Titles:        titles,
		PrimaryTitles: primary,
		URL:           fmt.Sprintf("https://myanimelist.net/anime/%d", a.ID),
		Cover:         cover,
		Description:   a.Synopsis,
		Score:         a.Score,
		Year:          year,
		Format:        strings.ToUpper(a.MediaType),
		EpisodeCount:  a.Episodes,
		MALID:         a.ID,
	}
}

type malRankingItem struct {
	Node malCatalogAnime `json:"node"`
}

type malRankingResponse struct {
	Data []malRankingItem `json:"data"`
}

type malSeasonResponse struct {
	Data []malRankingItem `json:"data"`
}

func (m *MALCatalog) Discover(ctx context.Context, now time.Time) (Discovery, error) {
	season := []string{"winter", "spring", "summer", "fall"}[(int(now.Month())-1)/3]
	key := fmt.Sprintf("discover:myanimelist:%d:%s", now.Year(), season)
	cached := Discovery{Trending: []domain.Anime{}, Seasonal: []domain.Anime{}}
	cachedOK, stale := false, false
	if m.Store != nil {
		cachedOK, stale = m.Store.CacheGet(key, &cached)
	}
	if cachedOK && !stale {
		return cached, nil
	}

	trending, trendingErr := m.ranking(ctx)
	seasonal, seasonalErr := m.season(ctx, now.Year(), season)
	out := Discovery{Trending: []domain.Anime{}, Seasonal: []domain.Anime{}}
	if trendingErr == nil {
		out.Trending = trending
	} else if cachedOK {
		out.Trending = cached.Trending
	}
	if seasonalErr == nil {
		out.Seasonal = seasonal
	} else if cachedOK {
		out.Seasonal = cached.Seasonal
	}

	if trendingErr != nil || seasonalErr != nil {
		if trendingErr != nil && seasonalErr != nil && !cachedOK {
			return out, errors.Join(trendingErr, seasonalErr)
		}
		out.Warning = "Algumas prateleiras do MyAnimeList não puderam ser atualizadas."
		if cachedOK {
			out.Warning = "MyAnimeList parcialmente indisponível; usando dados salvos onde necessário."
		}
	}
	if m.Store != nil && (trendingErr == nil || seasonalErr == nil) {
		_ = m.Store.CachePut(key, out, time.Hour, 7*24*time.Hour)
	}
	return out, nil
}

func (m *MALCatalog) ranking(ctx context.Context) ([]domain.Anime, error) {
	var response malRankingResponse
	err := m.get(ctx, "/anime/ranking", url.Values{
		"ranking_type": {"bypopularity"},
		"limit":        {"20"},
		"fields":       {malDiscoveryFields},
	}, &response)
	if err != nil {
		return nil, err
	}
	items := make([]domain.Anime, 0, len(response.Data))
	for _, entry := range response.Data {
		if entry.Node.ID > 0 && strings.TrimSpace(entry.Node.Title) != "" {
			items = append(items, entry.Node.model())
		}
	}
	return items, nil
}

func (m *MALCatalog) season(ctx context.Context, year int, season string) ([]domain.Anime, error) {
	var response malSeasonResponse
	err := m.get(ctx, fmt.Sprintf("/anime/season/%d/%s", year, season), url.Values{
		"sort":   {"anime_num_list_users"},
		"limit":  {"20"},
		"fields": {malDiscoveryFields},
	}, &response)
	if err != nil {
		return nil, err
	}
	items := make([]domain.Anime, 0, len(response.Data))
	for _, entry := range response.Data {
		if entry.Node.ID > 0 && strings.TrimSpace(entry.Node.Title) != "" {
			items = append(items, entry.Node.model())
		}
	}
	return items, nil
}

func (m *MALCatalog) get(ctx context.Context, path string, query url.Values, out any) error {
	if m.Client == nil {
		return fmt.Errorf("cliente HTTP do MyAnimeList não configurado")
	}
	if m.Gate != nil {
		if err := m.Gate.Wait(ctx); err != nil {
			return err
		}
	}
	base := strings.TrimRight(m.URL, "/")
	if base == "" {
		base = defaultMALAPIBase
	}
	clientID := strings.TrimSpace(m.ClientID)
	if clientID == "" {
		clientID = MALClientID
	}
	endpoint := base + "/" + strings.TrimLeft(path, "/") + "?" + query.Encode()
	return m.Client.JSON(ctx, "GET", endpoint, nil, map[string]string{"X-MAL-CLIENT-ID": clientID}, out)
}
