package manga

import (
	"archive/zip"
	"context"
	"fmt"
	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/platform"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

type Service struct {
	Client *netx.Client
	Base   string
	Gate   *netx.Gate
}

func New(c *netx.Client) *Service {
	return &Service{c, "https://api.mangadex.org", &netx.Gate{Interval: 250 * time.Millisecond}}
}
func pick(m map[string]string) string {
	for _, k := range []string{"pt-br", "pt", "en"} {
		if m[k] != "" {
			return m[k]
		}
	}
	keys := []string{}
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	if len(keys) > 0 {
		return m[keys[0]]
	}
	return ""
}
func (s *Service) get(ctx context.Context, path string, out any) error {
	if e := s.Gate.Wait(ctx); e != nil {
		return e
	}
	return s.Client.JSON(ctx, "GET", s.Base+path, nil, nil, out)
}
func (s *Service) Search(ctx context.Context, q string) ([]domain.Manga, error) {
	out := []domain.Manga{}
	for _, lang := range []string{"pt-br", ""} {
		params := url.Values{"title": {q}, "limit": {"30"}, "includes[]": {"cover_art"}, "contentRating[]": {"safe", "suggestive"}, "order[relevance]": {"desc"}}
		if lang != "" {
			params.Set("availableTranslatedLanguage[]", lang)
		}
		var r struct {
			Data []struct {
				ID         string `json:"id"`
				Attributes struct {
					Title       map[string]string `json:"title"`
					Description map[string]string `json:"description"`
					Status      string            `json:"status"`
					Languages   []string          `json:"availableTranslatedLanguages"`
				} `json:"attributes"`
				Relationships []struct {
					Type       string `json:"type"`
					Attributes struct {
						FileName string `json:"fileName"`
					} `json:"attributes"`
				} `json:"relationships"`
			} `json:"data"`
		}
		if e := s.get(ctx, "/manga?"+params.Encode(), &r); e != nil {
			return nil, e
		}
		for _, m := range r.Data {
			cover := ""
			for _, rel := range m.Relationships {
				if rel.Type == "cover_art" && rel.Attributes.FileName != "" {
					cover = "https://uploads.mangadex.org/covers/" + m.ID + "/" + rel.Attributes.FileName + ".256.jpg"
				}
			}
			out = append(out, domain.Manga{ID: m.ID, Title: pick(m.Attributes.Title), Description: pick(m.Attributes.Description), Cover: cover, Status: m.Attributes.Status, Languages: m.Attributes.Languages})
		}
		if len(out) > 0 {
			break
		}
	}
	return out, nil
}

type mangaListResponse struct {
	Data []struct {
		ID         string `json:"id"`
		Attributes struct {
			Title       map[string]string `json:"title"`
			Description map[string]string `json:"description"`
			Status      string            `json:"status"`
			Languages   []string          `json:"availableTranslatedLanguages"`
		} `json:"attributes"`
		Relationships []struct {
			Type       string `json:"type"`
			Attributes struct {
				FileName string `json:"fileName"`
			} `json:"attributes"`
		} `json:"relationships"`
	} `json:"data"`
}

func mangaFromResponse(response mangaListResponse) []domain.Manga {
	items := make([]domain.Manga, 0, len(response.Data))
	for _, item := range response.Data {
		cover := ""
		for _, relation := range item.Relationships {
			if relation.Type == "cover_art" && relation.Attributes.FileName != "" {
				root := "https://uploads.mangadex.org/covers/" + item.ID + "/" + relation.Attributes.FileName
				cover = root + ".256.jpg"
				break
			}
		}
		items = append(items, domain.Manga{
			ID:          item.ID,
			Title:       pick(item.Attributes.Title),
			Description: pick(item.Attributes.Description),
			Cover:       cover,
			Banner:      strings.Replace(cover, ".256.jpg", ".512.jpg", 1),
			Status:      item.Attributes.Status,
			Languages:   item.Attributes.Languages,
		})
	}
	return items
}

func (s *Service) list(ctx context.Context, params url.Values) ([]domain.Manga, error) {
	params.Set("limit", "20")
	params.Add("includes[]", "cover_art")
	params.Add("contentRating[]", "safe")
	params.Add("contentRating[]", "suggestive")
	var response mangaListResponse
	if err := s.get(ctx, "/manga?"+params.Encode(), &response); err != nil {
		return nil, err
	}
	return mangaFromResponse(response), nil
}

// Discover builds the MangaDex-backed shelves shown on the manga landing page.
// Manga catalogs do not have a dependable seasonal schedule, so the final shelf
// is based on the source's explicit publication status instead of inferred anime seasons.
func (s *Service) Discover(ctx context.Context) (domain.MangaDiscovery, error) {
	result := domain.MangaDiscovery{
		Featured:        []domain.Manga{},
		Popular:         []domain.Manga{},
		RecentlyUpdated: []domain.Manga{},
		Publishing:      []domain.Manga{},
		Categories:      []domain.MangaCategory{},
	}
	var wg sync.WaitGroup
	var mu sync.Mutex
	var failures []string
	load := func(name string, params url.Values, target *[]domain.Manga) {
		defer wg.Done()
		items, err := s.list(ctx, params)
		mu.Lock()
		defer mu.Unlock()
		if err != nil {
			failures = append(failures, name+": "+err.Error())
			return
		}
		*target = items
	}
	wg.Add(3)
	go load("mais populares", url.Values{"order[followedCount]": {"desc"}}, &result.Popular)
	go load("atualizações recentes", url.Values{"order[latestUploadedChapter]": {"desc"}}, &result.RecentlyUpdated)
	go load("em publicação", url.Values{"status[]": {"ongoing"}, "order[followedCount]": {"desc"}}, &result.Publishing)
	tags, tagErr := s.categories(ctx)
	result.Categories = tags
	wg.Wait()
	if len(result.Popular) > 0 {
		featuredCount := min(5, len(result.Popular))
		result.Featured = append(result.Featured, result.Popular[:featuredCount]...)
	}
	if tagErr != nil {
		failures = append(failures, "categorias: "+tagErr.Error())
	}
	if len(result.Popular)+len(result.RecentlyUpdated)+len(result.Publishing) == 0 {
		if len(failures) > 0 {
			return result, fmt.Errorf("não foi possível carregar a descoberta de mangás: %s", strings.Join(failures, "; "))
		}
		return result, fmt.Errorf("o catálogo não retornou mangás")
	}
	if len(failures) > 0 {
		result.Warning = "Algumas seções do catálogo não puderam ser atualizadas."
	}
	return result, nil
}

func (s *Service) categories(ctx context.Context) ([]domain.MangaCategory, error) {
	var response struct {
		Data []struct {
			ID         string `json:"id"`
			Attributes struct {
				Name  map[string]string `json:"name"`
				Group string            `json:"group"`
			} `json:"attributes"`
		} `json:"data"`
	}
	if err := s.get(ctx, "/manga/tag", &response); err != nil {
		return nil, err
	}
	preferred := []string{"Action", "Adventure", "Comedy", "Drama", "Fantasy", "Romance", "Sci-Fi", "Mystery", "Horror", "Thriller", "Slice of Life", "Sports", "Martial Arts", "Psychological"}
	localized := map[string]string{
		"action": "Ação", "adventure": "Aventura", "comedy": "Comédia", "drama": "Drama", "fantasy": "Fantasia",
		"romance": "Romance", "sci-fi": "Ficção científica", "mystery": "Mistério", "horror": "Terror", "thriller": "Suspense",
		"slice of life": "Cotidiano", "sports": "Esportes", "martial arts": "Artes marciais", "psychological": "Psicológico",
	}
	byName := make(map[string]domain.MangaCategory)
	for _, tag := range response.Data {
		if tag.Attributes.Group != "genre" {
			continue
		}
		name := pick(tag.Attributes.Name)
		if name == "" {
			continue
		}
		key := tag.Attributes.Name["en"]
		if key == "" {
			key = name
		}
		label := localized[strings.ToLower(key)]
		if label == "" {
			label = name
		}
		byName[strings.ToLower(key)] = domain.MangaCategory{ID: tag.ID, Name: label}
	}
	out := make([]domain.MangaCategory, 0, len(preferred))
	for _, name := range preferred {
		if category, ok := byName[strings.ToLower(name)]; ok {
			out = append(out, category)
		}
	}
	return out, nil
}

func (s *Service) ByCategory(ctx context.Context, categoryID string) ([]domain.Manga, error) {
	if strings.TrimSpace(categoryID) == "" {
		return nil, fmt.Errorf("selecione uma categoria válida")
	}
	return s.list(ctx, url.Values{
		"includedTags[]":       {categoryID},
		"order[followedCount]": {"desc"},
	})
}

func (s *Service) Chapters(ctx context.Context, id string) ([]domain.Chapter, error) {
	return s.ChaptersLanguage(ctx, id, "")
}
func (s *Service) ChaptersLanguage(ctx context.Context, id, language string) ([]domain.Chapter, error) {
	languages := []string{"pt-br", "en", "es-la", "es"}
	if language != "" {
		languages = []string{language}
	}
	for _, lang := range languages {
		out := []domain.Chapter{}
		seen := map[string]bool{}
		for offset := 0; ; offset += 500 {
			params := url.Values{"translatedLanguage[]": {lang}, "order[volume]": {"asc"}, "order[chapter]": {"asc"}, "limit": {"500"}, "offset": {strconv.Itoa(offset)}, "contentRating[]": {"safe", "suggestive"}, "includeExternalUrl": {"0"}}
			var r struct {
				Total int `json:"total"`
				Data  []struct {
					ID         string `json:"id"`
					Attributes struct {
						Title    string  `json:"title"`
						Chapter  string  `json:"chapter"`
						Volume   string  `json:"volume"`
						Pages    int     `json:"pages"`
						External *string `json:"externalUrl"`
					} `json:"attributes"`
					Relationships []struct {
						Type       string `json:"type"`
						Attributes struct {
							Name string `json:"name"`
						} `json:"attributes"`
					} `json:"relationships"`
				} `json:"data"`
			}
			if e := s.get(ctx, "/manga/"+url.PathEscape(id)+"/feed?"+params.Encode(), &r); e != nil {
				return nil, e
			}
			for _, ch := range r.Data {
				a := ch.Attributes
				key := a.Volume + ":" + a.Chapter
				if a.Chapter == "" {
					key = ch.ID
				}
				if seen[key] || a.Pages == 0 || a.External != nil {
					continue
				}
				seen[key] = true
				groups := []string{}
				for _, relationship := range ch.Relationships {
					if relationship.Type == "scanlation_group" && relationship.Attributes.Name != "" {
						groups = append(groups, relationship.Attributes.Name)
					}
				}
				out = append(out, domain.Chapter{ID: ch.ID, Title: a.Title, Number: a.Chapter, Volume: a.Volume, Language: lang, Pages: a.Pages, Group: strings.Join(groups, ", ")})
			}
			if offset+len(r.Data) >= r.Total || len(r.Data) == 0 {
				break
			}
		}
		if len(out) > 0 {
			return out, nil
		}
	}
	return []domain.Chapter{}, nil
}

type Page struct {
	URL          string
	Alternatives []string
}

func (s *Service) PageSources(ctx context.Context, id string) ([]Page, error) {
	if strings.TrimSpace(id) == "" {
		return nil, fmt.Errorf("capítulo sem identificador")
	}
	var r struct {
		Base    string `json:"baseUrl"`
		Chapter struct {
			Hash  string   `json:"hash"`
			Data  []string `json:"data"`
			Saver []string `json:"dataSaver"`
		} `json:"chapter"`
	}
	if e := s.get(ctx, "/at-home/server/"+url.PathEscape(id), &r); e != nil {
		return nil, e
	}
	base, err := url.Parse(r.Base)
	if err != nil || base.Host == "" || (base.Scheme != "http" && base.Scheme != "https") {
		return nil, fmt.Errorf("servidor de páginas retornou uma URL inválida")
	}
	if r.Chapter.Hash == "" {
		return nil, fmt.Errorf("servidor de páginas não retornou o hash do capítulo")
	}
	out := []Page{}
	count := max(len(r.Chapter.Data), len(r.Chapter.Saver))
	for i := 0; i < count; i++ {
		page := Page{}
		if i < len(r.Chapter.Data) && r.Chapter.Data[i] != "" {
			page.URL = strings.TrimRight(r.Base, "/") + "/data/" + url.PathEscape(r.Chapter.Hash) + "/" + url.PathEscape(r.Chapter.Data[i])
		}
		if i < len(r.Chapter.Saver) && r.Chapter.Saver[i] != "" {
			saverURL := strings.TrimRight(r.Base, "/") + "/data-saver/" + url.PathEscape(r.Chapter.Hash) + "/" + url.PathEscape(r.Chapter.Saver[i])
			if page.URL == "" {
				page.URL = saverURL
			} else {
				page.Alternatives = []string{saverURL}
			}
		}
		if page.URL != "" {
			out = append(out, page)
		}
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("capítulo sem páginas hospedadas")
	}
	return out, nil
}
func (s *Service) Pages(ctx context.Context, id string) ([]string, error) {
	pages, e := s.PageSources(ctx, id)
	if e != nil {
		return nil, e
	}
	out := []string{}
	for _, p := range pages {
		out = append(out, p.URL)
	}
	return out, nil
}
func (s *Service) Download(ctx context.Context, m domain.Manga, ch domain.Chapter, dir string, progress func(int, int)) (string, error) {
	pages, e := s.PageSources(ctx, ch.ID)
	if e != nil {
		return "", e
	}
	folder := filepath.Join(dir, "Manga", platform.SafeName(m.Title))
	if e = os.MkdirAll(folder, 0755); e != nil {
		return "", e
	}
	name := platform.SafeName("Vol."+ch.Volume+" Cap."+ch.Number+" "+ch.Title+" "+ch.Language+" "+ch.ID) + ".cbz"
	dest := filepath.Join(folder, name)
	if _, e = os.Stat(dest); e == nil {
		return dest, nil
	}
	f, e := os.CreateTemp(folder, ".chapter-*.part")
	if e != nil {
		return "", e
	}
	tmp := f.Name()
	defer os.Remove(tmp)
	z := zip.NewWriter(f)
	success := false
	defer func() {
		if !success {
			z.Close()
			f.Close()
		}
	}()
	for i, p := range pages {
		var r *http.Response
		var e error
		chosen := p.URL
		for _, u := range append([]string{p.URL}, p.Alternatives...) {
			r, e = s.Client.Do(ctx, "GET", u, nil, nil)
			if e == nil {
				chosen = u
				break
			}
			if ctx.Err() != nil {
				return "", ctx.Err()
			}
		}
		if e != nil {
			return "", fmt.Errorf("página %d do capítulo %s: %w", i+1, ch.ID, e)
		}
		ext := filepath.Ext(chosen)
		if len(ext) > 6 {
			ext = ".jpg"
		}
		w, e := z.Create(fmt.Sprintf("page_%05d%s", i+1, ext))
		if e != nil {
			r.Body.Close()
			return "", e
		}
		n, e := io.Copy(w, io.LimitReader(r.Body, (32<<20)+1))
		r.Body.Close()
		if e != nil {
			return "", e
		}
		if n > 32<<20 {
			return "", fmt.Errorf("página excede 32 MB")
		}
		if n == 0 {
			return "", fmt.Errorf("página vazia")
		}
		progress(i+1, len(pages))
	}
	if e = z.Close(); e != nil {
		return "", e
	}
	if e = f.Sync(); e != nil {
		return "", e
	}
	if e = f.Close(); e != nil {
		return "", e
	}
	success = true
	if e = platform.Publish(tmp, dest); e != nil {
		return "", e
	}
	return dest, nil
}
