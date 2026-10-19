package providers

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"
	"unicode"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/store"
	"golang.org/x/text/unicode/norm"
)

type Catalog struct {
	Providers []domain.AnimeProvider
	Store     *store.Store
}

func (c *Catalog) Provider(name string) (domain.AnimeProvider, error) {
	for _, p := range c.Providers {
		if p.Name() == name {
			return p, nil
		}
	}
	return nil, fmt.Errorf("esta opção não está disponível no momento")
}
func (c *Catalog) Search(ctx context.Context, q string, page int) (domain.SearchResult, error) {
	return c.SearchExpanded(ctx, q, page, nil)
}

type searchJob struct {
	provider int
	query    int
	result   domain.SearchResult
	err      error
}

// SearchExpanded searches the original query and a bounded set of multilingual
// aliases. Canonical IDs are assigned only when a provider title exactly matches
// one unambiguous metadata record; fuzzy similarity affects ordering only.
func (c *Catalog) SearchExpanded(ctx context.Context, q string, page int, matches []domain.Anime) (domain.SearchResult, error) {
	ctx, cancel := context.WithTimeout(ctx, 20*time.Second)
	defer cancel()
	queries := []string{strings.TrimSpace(q)}
	querySeen := map[string]bool{normalized(q): true}
	addQuery := func(title string) {
		title = strings.TrimSpace(title)
		key := normalized(title)
		if title == "" || querySeen[key] || len(queries) == 8 {
			return
		}
		querySeen[key] = true
		queries = append(queries, title)
	}
	intent := InferSearchIntent(q)
	intentTargetID := 0
	if intent.Season > 1 {
		targets := map[int]bool{}
		for _, match := range matches {
			if match.AniListID > 0 && metadataPrimaryTitleMatches(q, match) {
				targets[match.AniListID] = true
			}
		}
		if len(targets) == 1 {
			for id := range targets {
				intentTargetID = id
			}
		}
	}
	if intent.BaseTitle != "" {
		// Catalogs may index a sequel or year-marked adaptation under its base
		// title. Search that term separately; later matching still retains a
		// release-year suffix, while seasonal queries keep the requested season
		// for media preflight.
		addQuery(intent.BaseTitle)
	}
	// Give each AniList result one search slot before spending the remaining
	// budget on language aliases. This keeps related films and OVAs from being
	// crowded out by several titles belonging to the same adaptation.
	for _, match := range matches {
		addQuery(match.Title)
		if len(queries) == 8 {
			break
		}
	}
	if len(queries) < 8 {
		for _, match := range matches {
			for _, title := range append(append([]string{match.Title}, match.PrimaryTitles...), match.Titles...) {
				addQuery(title)
				if len(queries) == 8 {
					break
				}
			}
			if len(queries) == 8 {
				break
			}
		}
	}
	jobs := make(chan searchJob, len(c.Providers)*len(queries))
	for p := range c.Providers {
		for qi := range queries {
			jobs <- searchJob{provider: p, query: qi}
		}
	}
	close(jobs)
	responses := make(chan searchJob, len(c.Providers)*len(queries))
	workers := min(6, len(c.Providers)*len(queries))
	var wg sync.WaitGroup
	for range workers {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for job := range jobs {
				job.result, job.err = c.searchProvider(ctx, c.Providers[job.provider], queries[job.query], page)
				responses <- job
			}
		}()
	}
	go func() { wg.Wait(); close(responses) }()
	completed := make([]searchJob, 0, len(c.Providers)*len(queries))
	for job := range responses {
		completed = append(completed, job)
	}
	sort.Slice(completed, func(i, j int) bool {
		if completed[i].provider != completed[j].provider {
			return completed[i].provider < completed[j].provider
		}
		return completed[i].query < completed[j].query
	})
	out := domain.SearchResult{Items: []domain.Anime{}, Page: page, Warnings: []string{}}
	failed := 0
	for _, job := range completed {
		if job.err != nil {
			failed++
			continue
		}
		out.HasNext = out.HasNext || job.result.HasNext
		for _, item := range job.result.Items {
			if item.ID == "" {
				continue
			}
			item.AniListID, item.MALID = exactCanonical(item, matches)
			if item.Titles == nil {
				item.Titles = []string{}
			}
			if item.Title == "" {
				continue
			}
			item.MatchScore = searchSimilarity(q, item, matches)
			// Provider search endpoints can return unrelated titles alongside a
			// valid result. Keep exact canonical aliases and strong query matches;
			// metadata similarity alone must never make an unrelated card eligible.
			matchesOriginal := searchResultMatchesQuery(q, item, matches)
			matchesSeasonBase := intent.Season > 0 && intent.BaseTitle != "" &&
				normalized(queries[job.query]) == normalized(intent.BaseTitle) &&
				searchTitleMatchesQuery(intent.BaseTitle, item)
			if !matchesOriginal && !matchesSeasonBase {
				continue
			}
			if matchesSeasonBase {
				item.MatchScore = max(item.MatchScore, titleSimilarity(intent.BaseTitle, item.Title))
				if intentTargetID > 0 && item.AniListID != intentTargetID {
					// Treat the provider card as a provisional variant of the
					// requested season. Availability preflight must confirm that
					// season before the card is returned to the UI.
					item.AniListID = 0
					item.MALID = 0
					item.SearchGroupID = intentTargetID
				}
			}
			out.Items = append(out.Items, item)
		}
	}
	if failed == len(c.Providers)*len(queries) {
		if ctx.Err() != nil {
			return out, ctx.Err()
		}
		return out, fmt.Errorf("não foi possível pesquisar agora; tente novamente em instantes")
	}
	if failed > 0 {
		out.Warnings = append(out.Warnings, "Alguns resultados podem estar incompletos")
	}
	out.Items = mergeSearchResults(out.Items)
	sortSearchItems(out.Items)
	return out, nil
}

func (c *Catalog) searchProvider(ctx context.Context, provider domain.AnimeProvider, query string, page int) (domain.SearchResult, error) {
	key := catalogSearchCacheKey(provider.Name(), query, page)
	if c.Store != nil {
		var cached domain.SearchResult
		if ok, stale := c.Store.CacheGet(key, &cached); ok && !stale {
			return cached, nil
		}
	}
	result, err := provider.Search(ctx, query, page)
	if err != nil || ctx.Err() != nil || c.Store == nil {
		return result, err
	}
	soft, hard := 30*time.Second, 2*time.Minute
	if len(result.Items) == 0 {
		soft, hard = 10*time.Second, time.Minute
	}
	_ = c.Store.CachePut(key, result, soft, hard)
	return result, nil
}

func catalogSearchCacheKey(provider, query string, page int) string {
	identity := fmt.Sprintf("%s\x00%s\x00%d", provider, strings.Join(searchWords(query), " "), page)
	hash := sha256.Sum256([]byte(identity))
	return "catalog-search:" + hex.EncodeToString(hash[:])
}

// CanonicalizeDuplicateTitles attaches a metadata identity only to uncanonical
// cards whose displayed title is one of the exact duplicate title groups being
// resolved. It then merges those cards by the confirmed AniList ID.
func (c *Catalog) CanonicalizeDuplicateTitles(result domain.SearchResult, matches []domain.Anime, duplicateTitles []string) domain.SearchResult {
	titles := map[string]bool{}
	for _, title := range duplicateTitles {
		if key := normalized(title); key != "" {
			titles[key] = true
		}
	}
	for i := range result.Items {
		item := &result.Items[i]
		if item.AniListID > 0 || item.SearchGroupID > 0 || !titles[normalized(item.Title)] {
			continue
		}
		id, malID := exactCanonical(*item, matches)
		if id == 0 {
			id, malID = uniqueSeasonBasePrefixID(*item, matches)
		}
		if id > 0 {
			item.AniListID, item.MALID = id, malID
		}
	}
	result.Items = mergeSearchResults(result.Items)
	sortSearchItems(result.Items)
	return result
}

func uniqueSeasonBasePrefixID(item domain.Anime, matches []domain.Anime) (int, int) {
	itemWords := searchWords(item.Title)
	itemKey := normalized(item.Title)
	if len(itemWords) < 4 || len([]rune(itemKey)) < 18 {
		return 0, 0
	}
	baseCandidates := map[int]domain.Anime{}
	for _, sequel := range matches {
		intent := InferSearchIntent(sequel.Title)
		if sequel.AniListID <= 0 || intent.Season <= 1 {
			continue
		}
		baseKey := normalized(intent.BaseTitle)
		if !strings.HasPrefix(baseKey, itemKey) {
			continue
		}
		for _, base := range matches {
			if base.AniListID <= 0 || base.AniListID == sequel.AniListID {
				continue
			}
			primary := base.PrimaryTitles
			if len(primary) == 0 {
				primary = []string{base.Title}
			}
			for _, title := range primary {
				if normalized(title) == baseKey {
					baseCandidates[base.AniListID] = base
				}
			}
		}
	}
	if len(baseCandidates) != 1 {
		return 0, 0
	}
	for id, base := range baseCandidates {
		return id, base.MALID
	}
	return 0, 0
}

func sortSearchItems(items []domain.Anime) {
	sort.SliceStable(items, func(i, j int) bool {
		if (items[i].AniListID > 0) != (items[j].AniListID > 0) {
			return items[i].AniListID > 0
		}
		if items[i].MatchScore != items[j].MatchScore {
			return items[i].MatchScore > items[j].MatchScore
		}
		if normalized(items[i].Title) != normalized(items[j].Title) {
			return normalized(items[i].Title) < normalized(items[j].Title)
		}
		return items[i].Key() < items[j].Key()
	})
}

func searchTitleMatchesQuery(query string, item domain.Anime) bool {
	for _, title := range append([]string{item.Title}, item.Titles...) {
		if normalized(title) == normalized(query) || searchPhraseMatchesTitle(query, title) {
			return true
		}
	}
	return false
}

// SameSearchTitlePrefix reports a conservative long-prefix relation used only
// to discover possible cross-provider duplicates. Callers still need an exact
// unambiguous AniList identity before merging the results.
func SameSearchTitlePrefix(left, right string) bool {
	leftKey, rightKey := normalized(left), normalized(right)
	if leftKey == "" || rightKey == "" || leftKey == rightKey {
		return false
	}
	shorter, longer := leftKey, rightKey
	shorterOriginal := left
	if len([]rune(shorter)) > len([]rune(longer)) {
		shorter, longer = longer, shorter
		shorterOriginal = right
	}
	return len(searchWords(shorterOriginal)) >= 4 && len([]rune(shorter)) >= 18 && strings.HasPrefix(longer, shorter)
}

func searchResultMatchesQuery(query string, item domain.Anime, matches []domain.Anime) bool {
	rawQuery := query
	query = normalized(query)
	primaryMatches := map[int]bool{}
	for _, match := range matches {
		if match.AniListID > 0 && metadataPrimaryTitleMatches(rawQuery, match) {
			primaryMatches[match.AniListID] = true
		}
	}
	if item.AniListID > 0 {
		if primaryMatches[item.AniListID] || searchPhraseMatchesTitle(rawQuery, item.Title) {
			return true
		}
		if len(primaryMatches) > 0 {
			return false
		}
		// Allow a unique alternate spelling when no primary AniList title
		// matches the query. Ambiguous synonyms are not evidence of identity.
		matchingSynonyms := map[int]bool{}
		for _, match := range matches {
			if match.AniListID == 0 {
				continue
			}
			primary := match.PrimaryTitles
			if len(primary) == 0 {
				primary = []string{match.Title}
			}
			primarySet := map[string]bool{}
			for _, title := range primary {
				primarySet[normalized(title)] = true
			}
			for _, title := range match.Titles {
				if normalized(title) == query && !primarySet[query] {
					matchingSynonyms[match.AniListID] = true
				}
			}
		}
		return len(matchingSynonyms) == 1 && matchingSynonyms[item.AniListID]
	}
	for _, title := range append([]string{item.Title}, item.Titles...) {
		if normalized(title) == query {
			return true
		}
	}
	if searchPhraseMatchesTitle(rawQuery, item.Title) {
		return true
	}
	// Preserve typo tolerance for uncatalogued regional titles while rejecting
	// unrelated results that only resemble the query through edit distance.
	const minimumQuerySimilarity = 0.72
	best := titleSimilarity(query, item.Title)
	for _, title := range item.Titles {
		best = max(best, titleSimilarity(query, title))
	}
	return best >= minimumQuerySimilarity
}

func searchPhraseMatchesTitle(query, title string) bool {
	queryWords := searchWords(query)
	titleWords := searchWords(title)
	if len(queryWords) == 0 || len(titleWords) < len(queryWords) {
		return false
	}
	for start := 0; start+len(queryWords) <= len(titleWords); start++ {
		matched := true
		for offset, word := range queryWords {
			if titleWords[start+offset] != word {
				matched = false
				break
			}
		}
		if matched {
			return true
		}
	}
	return false
}

func searchWords(value string) []string {
	words := []string{}
	var current strings.Builder
	flush := func() {
		if current.Len() > 0 {
			words = append(words, current.String())
			current.Reset()
		}
	}
	for _, r := range norm.NFD.String(strings.ToLower(value)) {
		if unicode.IsMark(r) {
			continue
		}
		if r == '×' {
			flush()
			words = append(words, "x")
			continue
		}
		if unicode.IsLetter(r) || unicode.IsDigit(r) {
			current.WriteRune(r)
		} else {
			flush()
		}
	}
	flush()
	return words
}

func metadataPrimaryTitleMatches(query string, match domain.Anime) bool {
	queryKey := normalized(query)
	titles := match.PrimaryTitles
	if len(titles) == 0 {
		titles = []string{match.Title}
	}
	for _, title := range titles {
		key := normalized(title)
		if key == queryKey || searchPhraseMatchesTitle(query, title) || titleSimilarity(queryKey, title) >= 0.72 {
			return true
		}
	}
	return false
}

func exactCanonical(item domain.Anime, matches []domain.Anime) (int, int) {
	// The provider's displayed title is the strongest identity signal. An
	// alternate title can be generic and point at another adaptation (for
	// example, "Hunter x Hunter" alongside "HUNTER × HUNTER (2011)").
	primaryIDs := exactPrimaryTitleIDs([]string{item.Title}, matches)
	if len(primaryIDs) == 1 {
		for id, anime := range primaryIDs {
			return id, anime.MALID
		}
	}
	if len(primaryIDs) > 1 {
		return 0, 0
	}

	primaryIDs = exactPrimaryTitleIDs(item.Titles, matches)
	if len(primaryIDs) == 1 {
		for id, anime := range primaryIDs {
			return id, anime.MALID
		}
	}
	if len(primaryIDs) > 1 {
		return 0, 0
	}

	resultTitles := append([]string{item.Title}, item.Titles...)
	secondaryIDs := map[int]domain.Anime{}
	for _, candidate := range matches {
		if candidate.AniListID == 0 {
			continue
		}
		primaryTitles := candidate.PrimaryTitles
		if len(primaryTitles) == 0 {
			primaryTitles = []string{candidate.Title}
		}
		primarySet := map[string]bool{}
		for _, title := range primaryTitles {
			key := normalized(title)
			primarySet[key] = true
		}
		for _, title := range candidate.Titles {
			key := normalized(title)
			if key == "" || primarySet[key] {
				continue
			}
			for _, resultTitle := range resultTitles {
				if key == normalized(resultTitle) {
					secondaryIDs[candidate.AniListID] = candidate
				}
			}
		}
	}
	if len(secondaryIDs) != 1 {
		return 0, 0
	}
	for id, anime := range secondaryIDs {
		return id, anime.MALID
	}
	return 0, 0
}

func exactPrimaryTitleIDs(resultTitles []string, matches []domain.Anime) map[int]domain.Anime {
	ids := map[int]domain.Anime{}
	for _, candidate := range matches {
		if candidate.AniListID == 0 {
			continue
		}
		primaryTitles := candidate.PrimaryTitles
		if len(primaryTitles) == 0 {
			primaryTitles = []string{candidate.Title}
		}
		for _, primaryTitle := range primaryTitles {
			key := normalized(primaryTitle)
			if key == "" {
				continue
			}
			for _, resultTitle := range resultTitles {
				if key == normalized(resultTitle) {
					ids[candidate.AniListID] = candidate
				}
			}
		}
	}
	return ids
}

func searchSimilarity(query string, item domain.Anime, matches []domain.Anime) float64 {
	best := titleSimilarity(query, item.Title)
	for _, title := range item.Titles {
		best = max(best, titleSimilarity(query, title))
	}
	for _, match := range matches {
		for _, title := range append([]string{match.Title}, match.Titles...) {
			best = max(best, titleSimilarity(title, item.Title))
			for _, resultTitle := range item.Titles {
				best = max(best, titleSimilarity(title, resultTitle))
			}
		}
	}
	return best
}

func titleSimilarity(a, b string) float64 {
	a, b = normalized(a), normalized(b)
	if a == "" || b == "" {
		return 0
	}
	if a == b {
		return 1
	}
	ar, br := []rune(a), []rune(b)
	if len(ar) > 160 || len(br) > 160 {
		return 0
	}
	prev := make([]int, len(br)+1)
	for j := range prev {
		prev[j] = j
	}
	for i, x := range ar {
		cur := make([]int, len(br)+1)
		cur[0] = i + 1
		for j, y := range br {
			cost := 1
			if x == y {
				cost = 0
			}
			cur[j+1] = min(cur[j]+1, prev[j+1]+1, prev[j]+cost)
		}
		prev = cur
	}
	return 1 - float64(prev[len(br)])/float64(max(len(ar), len(br)))
}

func mergeSearchResults(items []domain.Anime) []domain.Anime {
	byKey := map[string]int{}
	byProviderURL := map[string]int{}
	byAniList := map[int]int{}
	out := make([]domain.Anime, 0, len(items))
	for _, item := range items {
		identityID := item.AniListID
		if identityID == 0 {
			identityID = item.SearchGroupID
		}
		urlKey := ""
		if strings.TrimSpace(item.URL) != "" {
			urlKey = item.Provider + ":" + strings.TrimRight(strings.TrimSpace(item.URL), "/")
		}
		idx, exists := byKey[item.Key()]
		if !exists && urlKey != "" {
			idx, exists = byProviderURL[urlKey]
		}
		if exists {
			if urlKey != "" {
				byProviderURL[urlKey] = idx
			}
			if item.MatchScore > out[idx].MatchScore {
				out[idx].MatchScore = item.MatchScore
			}
			if out[idx].AniListID == 0 && item.AniListID > 0 {
				out[idx].AniListID, out[idx].MALID = item.AniListID, item.MALID
				byAniList[item.AniListID] = idx
			}
			if out[idx].SearchGroupID == 0 && item.SearchGroupID > 0 {
				out[idx].SearchGroupID = item.SearchGroupID
				byAniList[item.SearchGroupID] = idx
			}
			continue
		}
		if identityID > 0 {
			if idx, ok := byAniList[identityID]; ok {
				if out[idx].Key() != item.Key() {
					present := false
					for _, variant := range out[idx].Variants {
						if variant.Key() == item.Key() {
							present = true
							break
						}
					}
					if !present {
						item.Variants = nil
						out[idx].Variants = append(out[idx].Variants, item)
						byKey[item.Key()] = idx
						if urlKey != "" {
							byProviderURL[urlKey] = idx
						}
					}
				}
				out[idx].MatchScore = max(out[idx].MatchScore, item.MatchScore)
				continue
			}
			byAniList[identityID] = len(out)
		}
		byKey[item.Key()] = len(out)
		if urlKey != "" {
			byProviderURL[urlKey] = len(out)
		}
		out = append(out, item)
	}
	return out
}
func (c *Catalog) Details(ctx context.Context, a domain.Anime) (domain.Detail, error) {
	original := a
	if a.Provider == "legacy" || a.Provider == "anilist" {
		matches := []domain.Anime{}
		queries := append([]string{a.Title}, a.Titles...)
		seen := map[string]bool{}
		for _, query := range queries {
			if query == "" || seen[query] {
				continue
			}
			seen[query] = true
			r, e := c.Search(ctx, query, 1)
			if e != nil {
				if ctx.Err() != nil {
					return domain.Detail{}, ctx.Err()
				}
				continue
			}
			for _, x := range r.Items {
				if SameTitle(a, x) {
					matches = append(matches, x)
				}
			}
			if len(matches) > 0 {
				break
			}
		}
		if len(matches) == 0 {
			return domain.Detail{}, fmt.Errorf("pesquise e selecione o título correspondente a %s no catálogo atual", a.Title)
		}
		a = matches[0]
	}
	if len(a.Variants) > 0 {
		candidates := append([]domain.Anime{a}, a.Variants...)
		type detailResult struct {
			domain.Detail
			quality int
			err     error
		}
		ctx, cancel := context.WithTimeout(ctx, 25*time.Second)
		defer cancel()
		results := make(chan detailResult, len(candidates))
		var wg sync.WaitGroup
		for _, candidate := range candidates {
			candidate := candidate
			wg.Add(1)
			go func() {
				defer wg.Done()
				p, err := c.Provider(candidate.Provider)
				if err != nil {
					results <- detailResult{err: err}
					return
				}
				key := "detail:" + candidate.Key()
				var d domain.Detail
				if ok, stale := c.Store.CacheGet(key, &d); ok && !stale {
					results <- detailResult{Detail: d, quality: seasonQuality(d.Episodes)}
					return
				}
				d, err = p.Details(ctx, candidate)
				if err == nil {
					c.Store.CachePut(key, d, 30*time.Minute, 24*time.Hour)
					results <- detailResult{Detail: d, quality: seasonQuality(d.Episodes)}
					return
				}
				results <- detailResult{err: err}
			}()
		}
		go func() { wg.Wait(); close(results) }()
		var best detailResult
		for result := range results {
			if result.err == nil && len(result.Episodes) > 0 && result.quality > best.quality {
				best = result
			}
		}
		if len(best.Episodes) > 0 {
			best.Anime.AniListID = a.AniListID
			best.Anime.MALID = a.MALID
			best.Anime.Variants = a.Variants
			return annotate(best.Detail, original), nil
		}
	}
	p, e := c.Provider(a.Provider)
	if e != nil {
		return domain.Detail{}, e
	}
	var d domain.Detail
	key := "detail:" + a.Key()
	if ok, stale := c.Store.CacheGet(key, &d); ok && !stale {
		return annotate(d, original), nil
	}
	d, e = p.Details(ctx, a)
	if e == nil {
		c.Store.CachePut(key, d, 30*time.Minute, 24*time.Hour)
	}
	return annotate(d, original), e
}

func seasonQuality(episodes []domain.Episode) int {
	seasons := map[int]bool{}
	for _, episode := range episodes {
		if episode.Season > 0 {
			seasons[episode.Season] = true
		}
	}
	return len(seasons)*10000 + len(episodes)
}
func normalized(title string) string {
	var b strings.Builder
	for _, r := range norm.NFD.String(strings.ToLower(title)) {
		if unicode.IsLetter(r) || unicode.IsDigit(r) {
			b.WriteRune(r)
		}
	}
	return b.String()
}
func SameTitle(a, b domain.Anime) bool {
	for _, x := range append([]string{a.Title}, a.Titles...) {
		if x == "" {
			continue
		}
		for _, y := range append([]string{b.Title}, b.Titles...) {
			if normalized(x) == normalized(y) {
				return true
			}
		}
	}
	return false
}
func annotate(d domain.Detail, original domain.Anime) domain.Detail {
	if SameTitle(d.Anime, original) {
		d.Anime.AniListID = original.AniListID
		d.Anime.MALID = original.MALID
		d.Anime.Season = original.Season
	}
	return d
}
func (c *Catalog) Resolve(ctx context.Context, ep domain.Episode, audio string) (domain.Stream, error) {
	p, e := c.Provider(ep.Provider)
	if e != nil {
		return domain.Stream{}, e
	}
	streams, e := p.Resolve(ctx, ep)
	if e != nil {
		return domain.Stream{}, e
	}
	preferred := strings.ToLower(strings.TrimSpace(audio))
	for _, s := range streams {
		if strings.EqualFold(strings.TrimSpace(s.Audio), preferred) {
			return s, nil
		}
	}
	for _, s := range streams {
		if preferred != "" && strings.Contains(strings.ToLower(s.Audio), preferred) {
			return s, nil
		}
	}
	if len(streams) > 0 {
		return streams[0], nil
	}
	return domain.Stream{}, fmt.Errorf("nenhuma fonte de vídeo disponível")
}

// ResolveCandidates returns the selected episode's streams first, followed by
// streams for the same episode from other catalog variants. It prefers an
// explicit season/number match; when provider season layouts differ, it accepts
// only a unique exact normalized episode-title match. Repeated titles are
// ambiguous and are never mapped by list position.
func (c *Catalog) ResolveCandidates(ctx context.Context, anime domain.Anime, ep domain.Episode, audio string) ([]domain.Stream, error) {
	var candidates []domain.Stream
	var failures []error
	type alternateResult struct {
		streams []domain.Stream
		err     error
	}

	primary, err := c.Provider(ep.Provider)
	if err != nil {
		return nil, err
	}
	// Start the selected source immediately. Discovery and resolution of an
	// alternate source can proceed even while the primary is slow or failing.
	primaryDone := make(chan alternateResult, 1)
	go func() {
		streams, resolveErr := primary.Resolve(ctx, ep)
		primaryDone <- alternateResult{streams: streams, err: resolveErr}
	}()

	variants := append([]domain.Anime{}, anime.Variants...)
	seen := map[string]bool{ep.Provider: true}
	for _, variant := range variants {
		if variant.Provider != "" {
			seen[variant.Provider] = true
		}
	}
	// Search may return a source without a canonical metadata match. In that
	// case discover only exact title/alias matches in other providers; fuzzy
	// ranking is intentionally not sufficient to map playback across sources.
	for _, provider := range c.Providers {
		if seen[provider.Name()] {
			continue
		}
		for _, title := range append([]string{anime.Title}, anime.Titles...) {
			if strings.TrimSpace(title) == "" {
				continue
			}
			result, searchErr := provider.Search(ctx, title, 1)
			if searchErr != nil {
				failures = append(failures, searchErr)
				continue
			}
			for _, item := range result.Items {
				if SameTitle(anime, item) {
					variants = append(variants, item)
				}
			}
			if len(variants) > len(anime.Variants) {
				break
			}
		}
		seen[provider.Name()] = true
	}
	resolvedVariants := map[string]bool{}
	var alternateJobs []struct {
		provider domain.AnimeProvider
		variant  domain.Anime
	}
	for _, variant := range variants {
		if variant.Provider == "" || variant.Provider == ep.Provider {
			continue
		}
		variantKey := variant.Key()
		if resolvedVariants[variantKey] {
			continue
		}
		resolvedVariants[variantKey] = true
		provider, err := c.Provider(variant.Provider)
		if err != nil {
			failures = append(failures, err)
			continue
		}
		alternateJobs = append(alternateJobs, struct {
			provider domain.AnimeProvider
			variant  domain.Anime
		}{provider: provider, variant: variant})
	}
	// Each provider is an independent fallback. Resolve them concurrently, but
	// gather results by their original order so the selected source stays stable.
	results := make([]alternateResult, len(alternateJobs))
	var wg sync.WaitGroup
	for i, job := range alternateJobs {
		wg.Add(1)
		go func(i int, job struct {
			provider domain.AnimeProvider
			variant  domain.Anime
		}) {
			defer wg.Done()
			detail, detailErr := job.provider.Details(ctx, job.variant)
			if detailErr != nil {
				results[i].err = detailErr
				return
			}
			alternate, ok := matchingEpisode(ep, detail.Episodes)
			if !ok {
				return
			}
			results[i].streams, results[i].err = job.provider.Resolve(ctx, alternate)
		}(i, job)
	}
	wg.Wait()
	primaryResult := <-primaryDone
	if primaryResult.err != nil {
		failures = append(failures, primaryResult.err)
	} else {
		candidates = append(candidates, sourceStreams(primaryResult.streams, ep.Provider)...)
	}
	for i, result := range results {
		if result.err != nil {
			failures = append(failures, result.err)
			continue
		}
		candidates = append(candidates, sourceStreams(result.streams, alternateJobs[i].provider.Name())...)
	}
	candidates = rankStreams(candidates, audio)
	candidates = dedupeStreams(candidates)
	if len(candidates) > 0 {
		return candidates, nil
	}
	if len(failures) > 0 {
		return nil, failures[0]
	}
	return nil, fmt.Errorf("nenhuma fonte de vídeo disponível para este episódio")
}

func sourceStreams(streams []domain.Stream, source string) []domain.Stream {
	out := make([]domain.Stream, 0, len(streams))
	for _, stream := range streams {
		if stream.Source == "" {
			stream.Source = source
		}
		out = append(out, stream)
	}
	return out
}

func dedupeStreams(streams []domain.Stream) []domain.Stream {
	seen := make(map[string]int, len(streams))
	out := make([]domain.Stream, 0, len(streams))
	for _, stream := range streams {
		urlKey := strings.TrimSpace(stream.URL)
		if urlKey == "" {
			continue
		}
		key := urlKey + "\x00" + streamHeadersKey(stream.Headers)
		if index, exists := seen[key]; exists {
			current := &out[index]
			current.Height = max(current.Height, stream.Height)
			current.Bandwidth = max(current.Bandwidth, stream.Bandwidth)
			current.Qualities = uniqueStrings(append(current.Qualities, stream.Qualities...))
			if current.Audio == "" {
				current.Audio = stream.Audio
			}
			if current.Source == "" {
				current.Source = stream.Source
			}
			continue
		}
		seen[key] = len(out)
		out = append(out, stream)
	}
	return out
}

func streamHeadersKey(headers map[string]string) string {
	entries := make([]string, 0, len(headers))
	for key, value := range headers {
		entries = append(entries, strings.ToLower(strings.TrimSpace(key))+":"+value)
	}
	sort.Strings(entries)
	return strings.Join(entries, "\n")
}

func uniqueStrings(values []string) []string {
	seen := make(map[string]bool, len(values))
	out := make([]string, 0, len(values))
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" || seen[value] {
			continue
		}
		seen[value] = true
		out = append(out, value)
	}
	return out
}

func rankStreams(streams []domain.Stream, audio string) []domain.Stream {
	if len(streams) < 2 {
		return streams
	}
	// The app performs the final cross-source ordering after HLS variant
	// discovery. Keep a stable audio preference here for callers of this method.
	preferred := strings.ToLower(strings.TrimSpace(audio))
	sort.SliceStable(streams, func(i, j int) bool {
		left := strings.ToLower(strings.TrimSpace(streams[i].Audio))
		right := strings.ToLower(strings.TrimSpace(streams[j].Audio))
		rank := func(label string) int {
			if preferred == "" || label == preferred {
				return 0
			}
			if strings.Contains(label, preferred) {
				return 1
			}
			return 2
		}
		return rank(left) < rank(right)
	})
	return streams
}

func matchingEpisode(source domain.Episode, candidates []domain.Episode) (domain.Episode, bool) {
	if source.Season > 0 && source.Number > 0 {
		var numbered []domain.Episode
		for _, candidate := range candidates {
			if candidate.Season == source.Season && candidate.Number == source.Number {
				numbered = append(numbered, candidate)
			}
		}
		if len(numbered) == 1 {
			return numbered[0], true
		}
		if len(numbered) > 1 {
			return domain.Episode{}, false
		}
	}

	// Providers sometimes divide the same work into different season groups.
	// A unique exact title can safely identify the same episode across those
	// layouts; a repeated title remains ambiguous and is never guessed.
	if source.Title == "" {
		return domain.Episode{}, false
	}
	var titled []domain.Episode
	for _, candidate := range candidates {
		if normalized(source.Title) == normalized(candidate.Title) {
			titled = append(titled, candidate)
		}
	}
	if len(titled) != 1 {
		return domain.Episode{}, false
	}
	return titled[0], true
}
