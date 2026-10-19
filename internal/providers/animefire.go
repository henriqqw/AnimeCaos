package providers

import (
	"context"
	"fmt"
	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
	"net/url"
	"sort"
	"strconv"
	"strings"
)

type AnimeFire struct {
	Client *netx.Client
	Base   string
}

func NewAnimeFire(c *netx.Client) *AnimeFire { return &AnimeFire{c, "https://api.animefire.one"} }
func (p *AnimeFire) Name() string            { return "animefire" }

type fireAnime struct {
	ID       string            `json:"id"`
	Titles   map[string]string `json:"titles"`
	Poster   string            `json:"poster_src"`
	Banner   string            `json:"backdrop_src"`
	Synopsis string            `json:"synopsis"`
	Audio    string            `json:"audio"`
	Status   string            `json:"status"`
	Score    float64           `json:"score"`
}

func (a fireAnime) model() domain.Anime {
	title := ""
	titles := []string{}
	for _, lang := range []string{"BR", "JP", "US"} {
		if t := a.Titles[lang]; t != "" {
			if title == "" {
				title = t
			}
			titles = append(titles, t)
		}
	}
	if title == "" {
		keys := []string{}
		for k := range a.Titles {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			titles = append(titles, a.Titles[k])
		}
		if len(titles) > 0 {
			title = titles[0]
		}
	}
	return domain.Anime{ID: a.ID, Provider: "animefire", Title: title, Titles: titles, URL: "https://animefire.one/anime/" + url.PathEscape(a.ID), Cover: a.Poster, Banner: a.Banner, Description: a.Synopsis, Audio: a.Audio, Status: a.Status, Score: a.Score}
}
func (p *AnimeFire) Search(ctx context.Context, q string, page int) (domain.SearchResult, error) {
	if page < 1 {
		page = 1
	}
	out := domain.SearchResult{Items: []domain.Anime{}, Page: page, Warnings: []string{}}
	if strings.TrimSpace(q) == "" {
		return out, fmt.Errorf("digite um termo de busca")
	}
	var r struct {
		Data []fireAnime `json:"data"`
		Meta struct {
			CurrentPage int    `json:"current_page"`
			LastPage    int    `json:"last_page"`
			HasMore     bool   `json:"has_more_pages"`
			Next        string `json:"next_page_url"`
		} `json:"meta"`
		Links struct {
			Next *string `json:"next"`
		} `json:"links"`
	}
	e := p.Client.JSON(ctx, "GET", p.Base+"/animes/pesquisar?"+url.Values{"q": {q}, "page": {strconv.Itoa(page)}, "v": {"3"}}.Encode(), nil, nil, &r)
	if e != nil {
		return out, e
	}
	for _, a := range r.Data {
		if a.ID != "" {
			out.Items = append(out.Items, a.model())
		}
	}
	out.HasNext = r.Meta.LastPage > page || r.Meta.HasMore || r.Meta.Next != "" || (r.Links.Next != nil && *r.Links.Next != "")
	return out, nil
}
func (p *AnimeFire) Details(ctx context.Context, a domain.Anime) (domain.Detail, error) {
	var r struct {
		Data struct {
			Hero     fireAnime `json:"hero"`
			Episodes []struct {
				ID     string  `json:"id"`
				Title  string  `json:"title"`
				Number float64 `json:"number"`
				Season int     `json:"season"`
				Audio  string  `json:"audio"`
			} `json:"episodes"`
		} `json:"data"`
	}
	e := p.Client.JSON(ctx, "GET", p.Base+"/anime/"+url.PathEscape(a.ID)+"?v=3", nil, nil, &r)
	if e != nil {
		return domain.Detail{}, e
	}
	if r.Data.Hero.ID == "" {
		return domain.Detail{}, fmt.Errorf("não foi possível carregar os detalhes deste anime")
	}
	d := domain.Detail{Anime: r.Data.Hero.model(), Episodes: []domain.Episode{}}
	for _, ep := range r.Data.Episodes {
		d.Episodes = append(d.Episodes, domain.Episode{ID: ep.ID, Provider: p.Name(), AnimeID: a.ID, Title: ep.Title, Number: ep.Number, Season: ep.Season, Audio: ep.Audio})
	}
	sort.SliceStable(d.Episodes, func(i, j int) bool {
		a, b := d.Episodes[i], d.Episodes[j]
		if a.Season != b.Season {
			return a.Season < b.Season
		}
		return a.Number < b.Number
	})
	d.Anime.EpisodeCount = len(d.Episodes)
	return d, nil
}
func (p *AnimeFire) Resolve(ctx context.Context, ep domain.Episode) ([]domain.Stream, error) {
	var r struct {
		Data struct {
			ID      string `json:"id"`
			Streams []struct {
				Audio     string   `json:"audio"`
				Offline   bool     `json:"is_offline"`
				URL       string   `json:"url"`
				Qualities []string `json:"qualities"`
			} `json:"streams"`
		} `json:"data"`
	}
	e := p.Client.JSON(ctx, "GET", p.Base+"/episode/"+url.PathEscape(ep.ID)+"?v=3", nil, nil, &r)
	if e != nil {
		return nil, e
	}
	out := []domain.Stream{}
	for _, s := range r.Data.Streams {
		if s.URL != "" && !s.Offline {
			out = append(out, domain.Stream{URL: s.URL, Kind: "hls", Audio: s.Audio, Qualities: s.Qualities, Headers: map[string]string{"Referer": "https://animefire.one/", "Origin": "https://animefire.one"}})
		}
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("este episódio está indisponível no momento")
	}
	return out, nil
}
