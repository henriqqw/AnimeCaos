package integrations

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/store"
	"html"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

type Metadata struct {
	Client    *netx.Client
	Store     *store.Store
	URL       string
	Gate      *netx.Gate
	mu        sync.Mutex
	pending   map[string][]lookupCall
	scheduled bool
	closed    bool
	ctx       context.Context
	cancel    context.CancelFunc
	wg        sync.WaitGroup
	slots     chan struct{}
}

func NewMetadata(c *netx.Client, s *store.Store) *Metadata {
	ctx, cancel := context.WithCancel(context.Background())
	return &Metadata{Client: c, Store: s, URL: "https://graphql.anilist.co", Gate: &netx.Gate{Interval: 2100 * time.Millisecond}, ctx: ctx, cancel: cancel, pending: map[string][]lookupCall{}, slots: make(chan struct{}, 3)}
}
func (m *Metadata) Query(ctx context.Context, q string, vars any, token string, out any) error {
	if e := m.Gate.Wait(ctx); e != nil {
		return e
	}
	h := map[string]string{}
	if token != "" {
		h["Authorization"] = "Bearer " + token
	}
	var r struct {
		Data   json.RawMessage `json:"data"`
		Errors []struct {
			Message string `json:"message"`
		} `json:"errors"`
	}
	e := m.Client.JSON(ctx, "POST", m.URL, map[string]any{"query": q, "variables": vars}, h, &r)
	if e != nil {
		var failure *netx.HTTPError
		if !errors.As(e, &failure) || failure.Status != 404 || json.Unmarshal(failure.Body, &r) != nil || len(r.Data) == 0 || string(r.Data) == "null" {
			return e
		}
	}
	if len(r.Errors) > 0 && len(r.Data) == 0 {
		return fmt.Errorf("AniList: %s", r.Errors[0].Message)
	}
	if len(r.Data) == 0 || string(r.Data) == "null" {
		return fmt.Errorf("AniList não retornou dados")
	}
	return json.Unmarshal(r.Data, out)
}

const mediaFields = `id idMal title { romaji english native } synonyms description coverImage { extraLarge large } bannerImage averageScore episodes format duration startDate { year }`

type aniMedia struct {
	ID    int `json:"id"`
	MAL   int `json:"idMal"`
	Title struct {
		Romaji  string `json:"romaji"`
		English string `json:"english"`
		Native  string `json:"native"`
	} `json:"title"`
	Synonyms    []string `json:"synonyms"`
	Description string   `json:"description"`
	Cover       struct {
		Extra string `json:"extraLarge"`
		Large string `json:"large"`
	} `json:"coverImage"`
	Banner    string  `json:"bannerImage"`
	Score     float64 `json:"averageScore"`
	Episodes  int     `json:"episodes"`
	Format    string  `json:"format"`
	StartDate struct {
		Year int `json:"year"`
	} `json:"startDate"`
}

var tags = regexp.MustCompile(`<[^>]*>`)

func (a aniMedia) model() domain.Anime {
	title := a.Title.Romaji
	if title == "" {
		title = a.Title.English
	}
	cover := a.Cover.Extra
	if cover == "" {
		cover = a.Cover.Large
	}
	primaryTitles := uniqueTitles(a.Title.Romaji, a.Title.English, a.Title.Native)
	titles := uniqueTitles(append(append([]string{}, primaryTitles...), a.Synonyms...)...)
	return domain.Anime{ID: strconv.Itoa(a.ID), Provider: "anilist", Title: title, Titles: titles, PrimaryTitles: primaryTitles, Cover: cover, Banner: a.Banner, Description: html.UnescapeString(tags.ReplaceAllString(a.Description, "")), Score: a.Score / 10, Year: a.StartDate.Year, Format: a.Format, EpisodeCount: a.Episodes, AniListID: a.ID, MALID: a.MAL, URL: "https://anilist.co/anime/" + strconv.Itoa(a.ID)}
}

func uniqueTitles(values ...string) []string {
	seen := map[string]bool{}
	out := make([]string, 0, len(values))
	for _, value := range values {
		value = strings.TrimSpace(value)
		key := strings.ToLower(value)
		if value == "" || seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, value)
	}
	return out
}

// TitleMatches resolves a typed title through AniList's multilingual title
// index. A preferred AniList ID skips text search and anchors home-card clicks
// to the exact work selected by the user.
func (m *Metadata) TitleMatches(ctx context.Context, query string, preferredID int) ([]domain.Anime, error) {
	if preferredID > 0 {
		var data struct {
			Media *aniMedia `json:"Media"`
		}
		graphql := `query($id:Int!){Media(id:$id,type:ANIME){` + mediaFields + `}}`
		if err := m.Query(ctx, graphql, map[string]any{"id": preferredID}, "", &data); err != nil {
			return nil, err
		}
		if data.Media == nil {
			return nil, fmt.Errorf("título selecionado não está disponível no catálogo")
		}
		return []domain.Anime{data.Media.model()}, nil
	}
	query = strings.TrimSpace(query)
	results, err := m.TitleMatchesBatch(ctx, []string{query})
	return results[query], err
}

// TitleMatchesBatch resolves multiple AniList searches in one GraphQL request.
// Search deduplication often needs the same lookup for several provider titles;
// batching avoids serial waits on AniList's request gate.
func (m *Metadata) TitleMatchesBatch(ctx context.Context, queries []string) (map[string][]domain.Anime, error) {
	type queryRef struct {
		original string
		aliases  []string
		key      string
		matches  []domain.Anime
		cached   bool
	}
	result := make(map[string][]domain.Anime, len(queries))
	unique := make([]queryRef, 0, len(queries))
	seen := map[string]int{}
	for _, query := range queries {
		query = strings.TrimSpace(query)
		if query == "" {
			continue
		}
		key := titleMatchesCacheKey(query)
		if index, exists := seen[key]; exists {
			unique[index].aliases = append(unique[index].aliases, query)
			continue
		}
		seen[key] = len(unique)
		queryRef := queryRef{original: query, aliases: []string{query}, key: key}
		if m.Store != nil {
			var cached []domain.Anime
			if ok, stale := m.Store.CacheGet(key, &cached); ok && !stale {
				queryRef.matches, queryRef.cached = cached, true
			}
		}
		unique = append(unique, queryRef)
	}
	if len(unique) == 0 {
		return result, nil
	}

	uncached := make([]queryRef, 0, len(unique))
	for _, query := range unique {
		if query.cached {
			for _, alias := range query.aliases {
				result[alias] = query.matches
			}
		} else {
			uncached = append(uncached, query)
		}
	}
	for start := 0; start < len(uncached); start += 8 {
		chunk := uncached[start:min(start+8, len(uncached))]
		definitions := make([]string, 0, len(chunk))
		fields := make([]string, 0, len(chunk))
		variables := make(map[string]any, len(chunk))
		for i, query := range chunk {
			variable := fmt.Sprintf("q%d", i)
			definitions = append(definitions, "$"+variable+":String!")
			fields = append(fields, fmt.Sprintf("r%d:Page(page:1,perPage:8){media(search:$%s,type:ANIME,isAdult:false,sort:SEARCH_MATCH){%s}}", i, variable, mediaFields))
			variables[variable] = query.original
		}
		graphql := "query(" + strings.Join(definitions, ",") + "){" + strings.Join(fields, " ") + "}"
		var data map[string]struct {
			Media []aniMedia `json:"media"`
		}
		if err := m.Query(ctx, graphql, variables, "", &data); err != nil {
			return result, err
		}
		for i, query := range chunk {
			mediaItems := data[fmt.Sprintf("r%d", i)].Media
			matches := make([]domain.Anime, 0, len(mediaItems))
			for _, item := range mediaItems {
				matches = append(matches, item.model())
			}
			for _, alias := range query.aliases {
				result[alias] = matches
			}
			if m.Store != nil {
				soft, hard := 30*time.Minute, 24*time.Hour
				if len(matches) == 0 {
					soft, hard = 2*time.Minute, 30*time.Minute
				}
				_ = m.Store.CachePut(query.key, matches, soft, hard)
			}
		}
	}
	return result, nil
}

func titleMatchesCacheKey(query string) string {
	hash := sha256.Sum256([]byte(strings.ToLower(strings.TrimSpace(query))))
	return "title-matches:v2:" + hex.EncodeToString(hash[:])
}

type Discovery struct {
	Trending []domain.Anime `json:"trending"`
	Seasonal []domain.Anime `json:"seasonal"`
	Warning  string         `json:"warning"`
}

func (m *Metadata) Discover(ctx context.Context) (Discovery, error) {
	out := Discovery{Trending: []domain.Anime{}, Seasonal: []domain.Anime{}}
	now := time.Now()
	season := []string{"WINTER", "SPRING", "SUMMER", "FALL"}[(int(now.Month())-1)/3]
	key := fmt.Sprintf("discover:%d:%s", now.Year(), season)
	ok, stale := m.Store.CacheGet(key, &out)
	if ok && !stale {
		return out, nil
	}
	var data struct {
		Trending struct {
			Media []aniMedia `json:"media"`
		} `json:"trending"`
		Seasonal struct {
			Media []aniMedia `json:"media"`
		} `json:"seasonal"`
	}
	q := `query($season:MediaSeason,$year:Int){trending:Page(perPage:20){media(type:ANIME,sort:TRENDING_DESC,isAdult:false){` + mediaFields + `}} seasonal:Page(perPage:20){media(type:ANIME,season:$season,seasonYear:$year,sort:POPULARITY_DESC,isAdult:false){` + mediaFields + `}}}`
	if e := m.Query(ctx, q, map[string]any{"season": season, "year": now.Year()}, "", &data); e != nil {
		out.Warning = e.Error()
		if ok {
			return out, nil
		}
		return out, e
	}
	out.Trending = []domain.Anime{}
	out.Seasonal = []domain.Anime{}
	for _, a := range data.Trending.Media {
		out.Trending = append(out.Trending, a.model())
	}
	for _, a := range data.Seasonal.Media {
		out.Seasonal = append(out.Seasonal, a.model())
	}
	out.Warning = ""
	m.Store.CachePut(key, out, 4*time.Hour, 7*24*time.Hour)
	return out, nil
}
func (m *Metadata) Batch(ctx context.Context, titles []string) (map[string]domain.Anime, error) {
	out := map[string]domain.Anime{}
	todo := []string{}
	for _, t := range titles {
		var a domain.Anime
		if ok, stale := m.Store.CacheGet("metadata:"+strings.ToLower(t), &a); ok && !stale {
			out[t] = a
		} else {
			todo = append(todo, t)
		}
	}
	for start := 0; start < len(todo); start += 10 {
		chunk := todo[start:min(start+10, len(todo))]
		defs := []string{}
		fields := []string{}
		vars := map[string]any{}
		for i, t := range chunk {
			v := fmt.Sprintf("s%d", i)
			defs = append(defs, "$"+v+":String")
			fields = append(fields, fmt.Sprintf("a%d:Media(search:$%s,type:ANIME){%s}", i, v, mediaFields))
			vars[v] = t
		}
		q := "query(" + strings.Join(defs, ",") + "){" + strings.Join(fields, " ") + "}"
		var data map[string]*aniMedia
		if e := m.Query(ctx, q, vars, "", &data); e != nil {
			return out, e
		}
		for i, t := range chunk {
			var a domain.Anime
			if v := data[fmt.Sprintf("a%d", i)]; v != nil {
				a = v.model()
			}
			out[t] = a
			m.Store.CachePut("metadata:"+strings.ToLower(t), a, 24*time.Hour, 7*24*time.Hour)
		}
	}
	return out, nil
}
func (m *Metadata) Lookup(ctx context.Context, title string) (domain.Anime, error) {
	key := strings.ToLower(title)
	var cached domain.Anime
	if ok, stale := m.Store.CacheGet("metadata:"+key, &cached); ok && !stale {
		return cached, nil
	}
	result := make(chan lookupResult, 1)
	m.mu.Lock()
	if m.closed {
		m.mu.Unlock()
		return domain.Anime{}, context.Canceled
	}
	m.pending[key] = append(m.pending[key], lookupCall{ctx: ctx, title: title, result: result})
	if !m.scheduled {
		m.scheduled = true
		m.wg.Add(1)
		time.AfterFunc(120*time.Millisecond, m.flush)
	}
	m.mu.Unlock()
	select {
	case <-ctx.Done():
		return domain.Anime{}, ctx.Err()
	case <-m.ctx.Done():
		return domain.Anime{}, context.Canceled
	case r := <-result:
		return r.anime, r.err
	}
}

type lookupResult struct {
	anime domain.Anime
	err   error
}
type lookupCall struct {
	ctx    context.Context
	title  string
	result chan lookupResult
}

func (m *Metadata) Close() { m.mu.Lock(); m.closed = true; m.cancel(); m.mu.Unlock(); m.wg.Wait() }
func (m *Metadata) flush() {
	defer m.wg.Done()
	m.mu.Lock()
	pending := m.pending
	m.pending = map[string][]lookupCall{}
	m.scheduled = false
	m.mu.Unlock()
	ctx, cancel := context.WithTimeout(m.ctx, 25*time.Second)
	defer cancel()
	select {
	case m.slots <- struct{}{}:
		defer func() { <-m.slots }()
	case <-ctx.Done():
		return
	}
	titles := []string{}
	active := map[string][]lookupCall{}
	for _, calls := range pending {
		for _, c := range calls {
			if c.ctx.Err() == nil {
				active[calls[0].title] = append(active[calls[0].title], c)
			}
		}
		if len(active[calls[0].title]) > 0 {
			titles = append(titles, calls[0].title)
		}
	}
	if len(titles) == 0 {
		return
	}
	values, err := m.Batch(ctx, titles)
	for title, calls := range active {
		for _, c := range calls {
			c.result <- lookupResult{values[title], err}
		}
	}
}
func (m *Metadata) Translate(ctx context.Context, text string) string {
	if text == "" {
		return ""
	}
	// Keep the original synopsis on failure; never truncate persisted metadata.
	if len([]rune(text)) > 1500 {
		chars := []rune(text)
		parts := []string{}
		for start := 0; start < len(chars); start += 1500 {
			parts = append(parts, m.Translate(ctx, string(chars[start:min(start+1500, len(chars))])))
		}
		return strings.Join(parts, "")
	}
	hash := sha256.Sum256([]byte(text))
	key := "translate:" + hex.EncodeToString(hash[:])
	var translated string
	if ok, _ := m.Store.CacheGet(key, &translated); ok {
		return translated
	}
	var r []json.RawMessage
	e := m.Client.JSON(ctx, "GET", "https://translate.googleapis.com/translate_a/single?"+url.Values{"client": {"gtx"}, "sl": {"auto"}, "tl": {"pt-BR"}, "dt": {"t"}, "q": {text}}.Encode(), nil, nil, &r)
	if e != nil || len(r) == 0 {
		return text
	}
	var parts [][]json.RawMessage
	if json.Unmarshal(r[0], &parts) != nil {
		return text
	}
	for _, p := range parts {
		if len(p) > 0 {
			var s string
			json.Unmarshal(p[0], &s)
			translated += s
		}
	}
	if translated == "" {
		return text
	}
	m.Store.CachePut(key, translated, 365*24*time.Hour, 3650*24*time.Hour)
	return translated
}
