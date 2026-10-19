package providers

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/store"
)

type fixtureProvider struct {
	name    string
	mu      sync.Mutex
	queries []string
	pages   []int
	items   map[string][]domain.Anime
	detail  domain.Detail
	streams map[string][]domain.Stream
	err     error
	hasNext bool
}

func (p *fixtureProvider) Name() string { return p.name }
func (p *fixtureProvider) Search(ctx context.Context, q string, page int) (domain.SearchResult, error) {
	if err := ctx.Err(); err != nil {
		return domain.SearchResult{}, err
	}
	p.mu.Lock()
	p.queries = append(p.queries, q)
	p.pages = append(p.pages, page)
	p.mu.Unlock()
	return domain.SearchResult{Items: p.items[q], Page: page, HasNext: p.hasNext}, nil
}
func (p *fixtureProvider) Details(context.Context, domain.Anime) (domain.Detail, error) {
	return p.detail, nil
}
func (p *fixtureProvider) Resolve(_ context.Context, ep domain.Episode) ([]domain.Stream, error) {
	return p.streams[ep.ID], p.err
}

func TestResolveCandidatesFallsBackToExactEpisodeInAlternateSource(t *testing.T) {
	primary := &fixtureProvider{name: "animefire", streams: map[string][]domain.Stream{}}
	alternate := &fixtureProvider{
		name: "animesonlinecc",
		detail: domain.Detail{Episodes: []domain.Episode{
			{ID: "s2e1", Provider: "animesonlinecc", Season: 2, Number: 1, Title: "A translated title"},
			{ID: "s3e1", Provider: "animesonlinecc", Season: 3, Number: 1, Title: "Another season"},
		}},
		streams: map[string][]domain.Stream{"s2e1": {
			{URL: "https://video.test/dub", Audio: "dublado"},
			{URL: "https://video.test/sub", Audio: "legendado"},
		}},
	}
	catalog := &Catalog{Providers: []domain.AnimeProvider{primary, alternate}}
	anime := domain.Anime{ID: "fire", Provider: "animefire", Title: "Same anime", Variants: []domain.Anime{{ID: "cc", Provider: "animesonlinecc", Title: "Same anime"}}}
	episode := domain.Episode{ID: "expired-fire-id", Provider: "animefire", Season: 2, Number: 1, Title: "Original title"}

	got, err := catalog.ResolveCandidates(context.Background(), anime, episode, "legendado")
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 || got[0].URL != "https://video.test/sub" || got[1].URL != "https://video.test/dub" {
		t.Fatalf("unexpected fallback candidates: %+v", got)
	}
}

func TestResolveCandidatesDoesNotGuessWhenEpisodeIsAmbiguous(t *testing.T) {
	primary := &fixtureProvider{name: "animefire"}
	alternate := &fixtureProvider{
		name: "animesonlinecc",
		detail: domain.Detail{Episodes: []domain.Episode{
			{ID: "a", Provider: "animesonlinecc", Title: "Episode One"},
			{ID: "b", Provider: "animesonlinecc", Title: "Episode One"},
		}},
		streams: map[string][]domain.Stream{"a": {{URL: "https://video.test/a"}}, "b": {{URL: "https://video.test/b"}}},
	}
	catalog := &Catalog{Providers: []domain.AnimeProvider{primary, alternate}}
	anime := domain.Anime{Provider: "animefire", Variants: []domain.Anime{{ID: "cc", Provider: "animesonlinecc"}}}
	got, err := catalog.ResolveCandidates(context.Background(), anime, domain.Episode{ID: "primary", Provider: "animefire", Title: "Episode One"}, "")
	if err == nil || len(got) != 0 {
		t.Fatalf("expected no guessed fallback, got %+v, err=%v", got, err)
	}
}

func TestDeduplicateStreamsMergesMetadataButKeepsDifferentRequestHeaders(t *testing.T) {
	got := dedupeStreams([]domain.Stream{
		{URL: "https://video.test/signed", Kind: "file", Audio: "legendado", Source: "animefire", Qualities: []string{"480p"}, Headers: map[string]string{"User-Agent": "browser"}},
		{URL: "https://video.test/signed", Kind: "file", Source: "animesonlinecc", Height: 1080, Bandwidth: 4_000_000, Qualities: []string{"1080p"}, Headers: map[string]string{"user-agent": "browser"}},
		{URL: "https://video.test/signed", Kind: "file", Source: "otakulogia", Headers: map[string]string{"User-Agent": "other"}},
	})
	if len(got) != 2 {
		t.Fatalf("same request should deduplicate but different user-agent must remain retryable: %+v", got)
	}
	if got[0].Height != 1080 || got[0].Bandwidth != 4_000_000 || len(got[0].Qualities) != 2 {
		t.Fatalf("duplicate URL discarded better quality metadata: %+v", got[0])
	}
}

func TestResolveCandidatesUsesUniqueEpisodeTitleAcrossDifferentSeasonLayouts(t *testing.T) {
	primary := &fixtureProvider{name: "animefire"}
	alternate := &fixtureProvider{
		name: "animesonlinecc",
		detail: domain.Detail{Episodes: []domain.Episode{
			{ID: "mapped", Provider: "animesonlinecc", Season: 1, Number: 24, Title: "The Same Episode"},
			{ID: "other", Provider: "animesonlinecc", Season: 2, Number: 2, Title: "Next Episode"},
		}},
		streams: map[string][]domain.Stream{"mapped": {{URL: "https://video.test/mapped"}}},
	}
	catalog := &Catalog{Providers: []domain.AnimeProvider{primary, alternate}}
	anime := domain.Anime{Provider: "animefire", Title: "Same anime", Variants: []domain.Anime{{ID: "cc", Provider: "animesonlinecc", Title: "Same anime"}}}
	episode := domain.Episode{ID: "fire-episode", Provider: "animefire", Season: 2, Number: 1, Title: "The Same Episode"}
	if mapped, ok := matchingEpisode(episode, alternate.detail.Episodes); !ok || mapped.ID != "mapped" {
		t.Fatalf("unique title did not map across season layouts: %+v, %t", mapped, ok)
	}

	got, err := catalog.ResolveCandidates(context.Background(), anime, episode, "")
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].URL != "https://video.test/mapped" {
		t.Fatalf("expected unique title match across season layouts, got %+v", got)
	}
}

func TestResolveCandidatesDoesNotUseRepeatedTitleAcrossSeasonLayouts(t *testing.T) {
	primary := &fixtureProvider{name: "animefire"}
	alternate := &fixtureProvider{
		name: "animesonlinecc",
		detail: domain.Detail{Episodes: []domain.Episode{
			{ID: "a", Provider: "animesonlinecc", Season: 1, Number: 24, Title: "The Same Episode"},
			{ID: "b", Provider: "animesonlinecc", Season: 2, Number: 1, Title: "The Same Episode"},
		}},
		streams: map[string][]domain.Stream{"a": {{URL: "https://video.test/a"}}, "b": {{URL: "https://video.test/b"}}},
	}
	catalog := &Catalog{Providers: []domain.AnimeProvider{primary, alternate}}
	anime := domain.Anime{Provider: "animefire", Title: "Same anime", Variants: []domain.Anime{{ID: "cc", Provider: "animesonlinecc", Title: "Same anime"}}}
	episode := domain.Episode{ID: "fire-episode", Provider: "animefire", Season: 3, Number: 1, Title: "The Same Episode"}

	got, err := catalog.ResolveCandidates(context.Background(), anime, episode, "")
	if err == nil || len(got) != 0 {
		t.Fatalf("expected ambiguous fallback to be rejected, got %+v, err=%v", got, err)
	}
}

func TestResolveCandidatesDiscoversExactAliasWhenSearchOmittedVariants(t *testing.T) {
	primary := &fixtureProvider{name: "animefire"}
	alternate := &fixtureProvider{
		name:    "animesonlinecc",
		items:   map[string][]domain.Anime{"Cyberpunk: Edgerunners": {{ID: "cc", Provider: "animesonlinecc", Title: "Cyberpunk: Edgerunners"}}},
		detail:  domain.Detail{Episodes: []domain.Episode{{ID: "cc-ep1", Provider: "animesonlinecc", Season: 1, Number: 1}}},
		streams: map[string][]domain.Stream{"cc-ep1": {{URL: "https://video.test/cc-ep1"}}},
	}
	catalog := &Catalog{Providers: []domain.AnimeProvider{primary, alternate}}
	anime := domain.Anime{ID: "fire", Provider: "animefire", Title: "Cyberpunk: Mercenários", Titles: []string{"Cyberpunk: Edgerunners"}}
	episode := domain.Episode{ID: "fire-ep1", Provider: "animefire", Season: 1, Number: 1}

	got, err := catalog.ResolveCandidates(context.Background(), anime, episode, "")
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].URL != "https://video.test/cc-ep1" {
		t.Fatalf("expected exact alias fallback, got %+v", got)
	}
}

func TestSearchExpandedUsesCanonicalAliasesAndMergesProviderVariants(t *testing.T) {
	canonical := domain.Anime{Title: "Kimetsu no Yaiba", Titles: []string{"Kimetsu no Yaiba", "Demon Slayer", "鬼滅の刃"}, PrimaryTitles: []string{"Kimetsu no Yaiba", "Demon Slayer", "鬼滅の刃"}, AniListID: 101}
	a := domain.Anime{ID: "fire-1", Provider: "animefire", Title: "Demon Slayer"}
	b := domain.Anime{ID: "cc-1", Provider: "animesonlinecc", Title: "Kimetsu no Yaiba"}
	first := &fixtureProvider{name: "animefire", items: map[string][]domain.Anime{"鬼滅の刃": {a}}}
	second := &fixtureProvider{name: "animesonlinecc", items: map[string][]domain.Anime{"Kimetsu no Yaiba": {b}}}
	catalog := &Catalog{Providers: []domain.AnimeProvider{first, second}}
	r, err := catalog.SearchExpanded(context.Background(), "鬼滅の刃", 1, []domain.Anime{canonical})
	if err != nil {
		t.Fatal(err)
	}
	if len(r.Items) != 1 {
		t.Fatalf("got %d results, want one merged work", len(r.Items))
	}
	if r.Items[0].AniListID != 101 {
		t.Fatalf("canonical identity not assigned: %+v", r.Items[0])
	}
	if len(r.Items[0].Variants) != 1 {
		t.Fatalf("got %d provider variants, want 1", len(r.Items[0].Variants))
	}
	first.mu.Lock()
	foundJP := false
	for _, q := range first.queries {
		if q == "鬼滅の刃" {
			foundJP = true
		}
	}
	first.mu.Unlock()
	if !foundJP {
		t.Fatal("native title was not queried")
	}
}

func TestSearchExpandedCachesProviderPageBriefly(t *testing.T) {
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	provider := &fixtureProvider{name: "animefire", items: map[string][]domain.Anime{
		"Cache Sample": {{ID: "sample", Provider: "animefire", Title: "Cache Sample"}},
	}}
	catalog := &Catalog{Providers: []domain.AnimeProvider{provider}, Store: db}
	for i := 0; i < 2; i++ {
		result, searchErr := catalog.SearchExpanded(context.Background(), "Cache Sample", 1, nil)
		if searchErr != nil || len(result.Items) != 1 {
			t.Fatalf("search %d returned %+v, %v", i+1, result, searchErr)
		}
	}
	provider.mu.Lock()
	defer provider.mu.Unlock()
	if len(provider.queries) != 1 {
		t.Fatalf("identical page was fetched %d times; want one provider request", len(provider.queries))
	}
}

func TestSearchExpandedDoesNotCanonicalizeAmbiguousTitles(t *testing.T) {
	a := domain.Anime{Title: "Same Name", AniListID: 10}
	b := domain.Anime{Title: "Same Name", AniListID: 20}
	p := &fixtureProvider{name: "animefire", items: map[string][]domain.Anime{"Same Name": {{ID: "x", Provider: "animefire", Title: "Same Name"}}}}
	r, err := (&Catalog{Providers: []domain.AnimeProvider{p}}).SearchExpanded(context.Background(), "Same Name", 1, []domain.Anime{a, b})
	if err != nil {
		t.Fatal(err)
	}
	if len(r.Items) != 1 || r.Items[0].AniListID != 0 {
		t.Fatalf("ambiguous title received unsafe canonical identity: %+v", r.Items)
	}
}

func TestExactCanonicalPrefersProviderTitleOverAmbiguousAlias(t *testing.T) {
	remake1999 := domain.Anime{
		Title:         "HUNTER×HUNTER",
		PrimaryTitles: []string{"HUNTER×HUNTER", "Hunter x Hunter"},
		AniListID:     136,
	}
	remake2011 := domain.Anime{
		Title:         "HUNTER×HUNTER (2011)",
		PrimaryTitles: []string{"HUNTER×HUNTER (2011)", "Hunter x Hunter (2011)"},
		AniListID:     11061,
	}
	matches := []domain.Anime{remake1999, remake2011}
	providerResult := domain.Anime{Title: "HUNTER × HUNTER (2011)", Titles: []string{"Hunter x Hunter"}}

	id, _ := exactCanonical(providerResult, matches)
	if id != remake2011.AniListID {
		t.Fatalf("provider title was assigned AniList ID %d; want 2011 adaptation ID %d", id, remake2011.AniListID)
	}
	providerResult.AniListID = id
	if !searchResultMatchesQuery("hunter", providerResult, matches) {
		t.Fatal("the canonical 2011 result was rejected for the broad hunter query")
	}

	oldResult := domain.Anime{Title: "Hunter x Hunter"}
	oldID, _ := exactCanonical(oldResult, matches)
	if oldID != remake1999.AniListID {
		t.Fatalf("generic provider title was assigned AniList ID %d; want the unambiguous 1999 title ID %d", oldID, remake1999.AniListID)
	}
}

func TestSearchExpandedRejectsUnrelatedPlayableTitles(t *testing.T) {
	canonical := domain.Anime{Title: "Kimetsu no Yaiba", Titles: []string{"Kimetsu no Yaiba", "Demon Slayer"}, PrimaryTitles: []string{"Kimetsu no Yaiba", "Demon Slayer"}, AniListID: 101}
	provider := &fixtureProvider{name: "animefire", items: map[string][]domain.Anime{
		"Demon Slayer": {
			{ID: "correct", Provider: "animefire", Title: "Kimetsu no Yaiba"},
			{ID: "onigiri", Provider: "animefire", Title: "Onigiri"},
			{ID: "girlfriend", Provider: "animefire", Title: "My Girlfriend's Friend"},
		},
	}}
	result, err := (&Catalog{Providers: []domain.AnimeProvider{provider}}).SearchExpanded(context.Background(), "Demon Slayer", 1, []domain.Anime{canonical})
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Items) != 1 || result.Items[0].Title != "Kimetsu no Yaiba" || result.Items[0].AniListID != canonical.AniListID {
		t.Fatalf("unrelated playable results escaped the canonical title filter: %+v", result.Items)
	}
}

func TestSearchExpandedIgnoresAmbiguousAniListSynonym(t *testing.T) {
	onigiri := domain.Anime{Title: "Onigiri", Titles: []string{"Onigiri", "Demon Slayer"}, PrimaryTitles: []string{"Onigiri", "鬼斬"}, AniListID: 21612}
	kimetsu := domain.Anime{Title: "Kimetsu no Yaiba", Titles: []string{"Kimetsu no Yaiba", "Demon Slayer: Kimetsu no Yaiba"}, PrimaryTitles: []string{"Kimetsu no Yaiba", "Demon Slayer: Kimetsu no Yaiba", "鬼滅の刃"}, AniListID: 101922}
	provider := &fixtureProvider{name: "animefire", items: map[string][]domain.Anime{
		"Demon Slayer": {
			{ID: "onigiri", Provider: "animefire", Title: "Onigiri"},
			{ID: "kimetsu", Provider: "animefire", Title: "Demon Slayer: Kimetsu no Yaiba"},
		},
	}}
	result, err := (&Catalog{Providers: []domain.AnimeProvider{provider}}).SearchExpanded(context.Background(), "Demon Slayer", 1, []domain.Anime{onigiri, kimetsu})
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Items) != 1 || result.Items[0].AniListID != kimetsu.AniListID {
		t.Fatalf("ambiguous synonym caused the wrong identity to escape search: %+v", result.Items)
	}
}

func TestSearchCardsReceiveOnlyTheirExactCanonicalDisplayMetadata(t *testing.T) {
	old := domain.Anime{Title: "HUNTER×HUNTER", PrimaryTitles: []string{"HUNTER×HUNTER", "Hunter x Hunter"}, AniListID: 136, Year: 1999, Format: "TV", EpisodeCount: 62}
	newer := domain.Anime{Title: "HUNTER×HUNTER (2011)", PrimaryTitles: []string{"HUNTER×HUNTER (2011)", "Hunter x Hunter 2011"}, AniListID: 11061, Year: 2011, Format: "TV", EpisodeCount: 148}
	provider := &fixtureProvider{name: "animesonlinecc", items: map[string][]domain.Anime{
		"hunter": {
			{ID: "old", Provider: "animesonlinecc", Title: "Hunter x Hunter"},
			{ID: "new", Provider: "animesonlinecc", Title: "Hunter x Hunter 2011"},
		},
	}}
	result, err := (&Catalog{Providers: []domain.AnimeProvider{provider}}).SearchExpanded(context.Background(), "hunter", 1, []domain.Anime{old, newer})
	if err != nil {
		t.Fatal(err)
	}
	byID := make(map[int]domain.Anime, len(result.Items))
	for _, item := range result.Items {
		if item.AniListID > 0 {
			byID[item.AniListID] = item
		}
	}
	if got := byID[136]; got.Year != 1999 || got.EpisodeCount != 62 {
		t.Errorf("1999 card lost or received incorrect metadata: %+v", got)
	}
	if got := byID[11061]; got.Year != 2011 || got.EpisodeCount != 148 {
		t.Errorf("2011 card lost or received incorrect metadata: %+v", got)
	}
}

func TestSearchExpandedSpreadsQueryBudgetAcrossAniListResults(t *testing.T) {
	matches := []domain.Anime{
		{Title: "Hunter"},
		{Title: "HUNTER×HUNTER"},
		{Title: "HUNTER×HUNTER OVA"},
		{Title: "HUNTER×HUNTER (2011)"},
		{Title: "THE HUNTER"},
		{Title: "HUNTER×HUNTER Pilot-ban"},
		{Title: "HUNTER×HUNTER: The Last Mission", Titles: []string{"The Last Mission"}},
		{Title: "HUNTER×HUNTER: Greed Island", Titles: []string{"Greed Island"}},
	}
	provider := &fixtureProvider{name: "animefire", items: map[string][]domain.Anime{}}
	_, err := (&Catalog{Providers: []domain.AnimeProvider{provider}}).SearchExpanded(context.Background(), "hunter", 1, matches)
	if err != nil {
		t.Fatal(err)
	}
	provider.mu.Lock()
	defer provider.mu.Unlock()
	if len(provider.queries) != 8 {
		t.Fatalf("query budget changed: got %d terms: %v", len(provider.queries), provider.queries)
	}
	for _, title := range []string{"HUNTER×HUNTER: The Last Mission", "HUNTER×HUNTER: Greed Island"} {
		found := false
		for _, query := range provider.queries {
			if query == title {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("related work %q was crowded out of the AniList query budget: %v", title, provider.queries)
		}
	}
}

func TestSearchExpandedFallsBackToBaseTitleForExplicitSeasonWithoutMergingIdentity(t *testing.T) {
	query := "Tensei Shitara Ken Deshita 2nd Season"
	canonical := domain.Anime{
		Title:         query,
		PrimaryTitles: []string{query, "Reincarnated as a Sword Season 2"},
		Titles:        []string{query, "Reincarnated as a Sword Season 2"},
		AniListID:     159042,
	}
	provider := &fixtureProvider{name: "animesonlinecc", items: map[string][]domain.Anime{
		"Tensei Shitara Ken Deshita": {
			{ID: "series", Provider: "animesonlinecc", Title: "Tensei Shitara Ken Deshita"},
			{ID: "neighbor", Provider: "animesonlinecc", Title: "Tensei Shitara Dragon no Tamago Datta"},
		},
	}}
	secondProvider := &fixtureProvider{name: "otakulogia", items: map[string][]domain.Anime{
		"Tensei Shitara Ken Deshita": {{ID: "series-2", Provider: "otakulogia", Title: "Tensei Shitara Ken Deshita"}},
	}}
	result, err := (&Catalog{Providers: []domain.AnimeProvider{provider, secondProvider}}).SearchExpanded(context.Background(), query, 1, []domain.Anime{canonical})
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Items) != 1 || result.Items[0].ID != "series" || len(result.Items[0].Variants) != 1 {
		t.Fatalf("expected one provisional card with both provider variants and no neighbor title, got %+v", result.Items)
	}
	if result.Items[0].AniListID != 0 || result.Items[0].SearchGroupID != canonical.AniListID {
		t.Fatalf("season identity must stay provisional until requested-season preflight succeeds: %+v", result.Items[0])
	}
	provider.mu.Lock()
	defer provider.mu.Unlock()
	foundBaseQuery := false
	for _, term := range provider.queries {
		if term == "Tensei Shitara Ken Deshita" {
			foundBaseQuery = true
		}
	}
	if !foundBaseQuery {
		t.Fatalf("provider did not receive normalized base-title query: %v", provider.queries)
	}
}

func TestInferSearchIntentRecognizesSeasonSuffixes(t *testing.T) {
	for _, sample := range []struct {
		query  string
		base   string
		season int
	}{
		{"Tensei Shitara Ken Deshita 2nd Season", "Tensei Shitara Ken Deshita", 2},
		{"One Punch Man Season 2", "One Punch Man", 2},
		{"One Punch Man 2ª temporada", "One Punch Man", 2},
		{"One Punch Man S2", "One Punch Man", 2},
		{"転生したら剣でした 第2期", "転生したら剣でした", 2},
	} {
		intent := InferSearchIntent(sample.query)
		if intent.BaseTitle != sample.base || intent.Season != sample.season {
			t.Errorf("InferSearchIntent(%q)=%+v, want base=%q season=%d", sample.query, intent, sample.base, sample.season)
		}
	}
	if intent := InferSearchIntent("Hunter x Hunter (2011)"); intent.Season != 0 || intent.BaseTitle != "Hunter x Hunter" || intent.Year != 2011 {
		t.Fatalf("year/adaptation marker should preserve its year and base title without becoming a season: %+v", intent)
	}
}

func TestSearchExpandedUsesBaseForReleaseYearButKeepsYearMatch(t *testing.T) {
	for _, query := range []string{"Hunter x Hunter 2011", "Hunter x Hunter (2011)"} {
		provider := &fixtureProvider{name: "otakulogia", items: map[string][]domain.Anime{
			"Hunter x Hunter": {
				{ID: "hxh-2011", Provider: "otakulogia", Title: "HUNTER × HUNTER (2011)"},
				{ID: "hxh-1999", Provider: "otakulogia", Title: "HUNTER × HUNTER"},
			},
		}}
		result, err := (&Catalog{Providers: []domain.AnimeProvider{provider}}).SearchExpanded(context.Background(), query, 1, nil)
		if err != nil {
			t.Fatal(err)
		}
		if len(result.Items) != 1 || result.Items[0].ID != "hxh-2011" {
			t.Fatalf("release-year search %q should return only the matching adaptation: %+v", query, result.Items)
		}
		provider.mu.Lock()
		foundBaseQuery := false
		for _, term := range provider.queries {
			if term == "Hunter x Hunter" {
				foundBaseQuery = true
				break
			}
		}
		provider.mu.Unlock()
		if !foundBaseQuery {
			t.Fatalf("provider did not receive the base-title query for %q: %v", query, provider.queries)
		}
	}
}

func TestCanonicalizeDuplicateTitlesMergesOnlyAnUnambiguousAniListWork(t *testing.T) {
	baseTitle := "Tensei Shitara Dai Nana Ouji Datta node, Kimamani Majutsu wo Kiwamemasu"
	series := domain.Anime{
		Title:         baseTitle,
		PrimaryTitles: []string{baseTitle},
		Titles:        []string{baseTitle, "I Was Reincarnated as the 7th Prince"},
		AniListID:     156415,
	}
	sequelTitle := baseTitle + " 2nd Season"
	sequel := domain.Anime{Title: sequelTitle, PrimaryTitles: []string{sequelTitle}, AniListID: 178090}
	items := []domain.Anime{
		{ID: "cc", Provider: "animesonlinecc", Title: "Tensei shitara Dainana Ouji Datta node, Kimama ni Majutsu wo Kiwamemasu"},
		{ID: "otaku", Provider: "otakulogia", Title: "Tensei Shitara Dai Nana Ouji Dattanode, Kimamani Majutsu wo Kiwamemasu"},
		{ID: "sushi", Provider: "sushianimes", Title: "Tensei shitara Dainana Ouji"},
	}
	catalog := &Catalog{}
	result := catalog.CanonicalizeDuplicateTitles(domain.SearchResult{Items: items, Page: 1}, []domain.Anime{series, sequel}, []string{items[0].Title, items[1].Title, items[2].Title})
	if len(result.Items) != 1 || result.Items[0].AniListID != series.AniListID || len(result.Items[0].Variants) != 2 {
		t.Fatalf("exact AniList identity should consolidate duplicate providers: %+v", result.Items)
	}

	ambiguous := []domain.Anime{
		{Title: "Same Name", PrimaryTitles: []string{"Same Name"}, AniListID: 1},
		{Title: "Same Name", PrimaryTitles: []string{"Same Name"}, AniListID: 2},
	}
	ambiguousItems := []domain.Anime{
		{ID: "one", Provider: "animesonlinecc", Title: "Same Name"},
		{ID: "two", Provider: "otakulogia", Title: "Same Name"},
	}
	keptSeparate := catalog.CanonicalizeDuplicateTitles(domain.SearchResult{Items: ambiguousItems}, ambiguous, []string{"Same Name"})
	if len(keptSeparate.Items) != 2 {
		t.Fatalf("ambiguous metadata must not merge same-text remakes: %+v", keptSeparate.Items)
	}
}

func TestSameSearchTitlePrefixIsOnlyADiscoveryHint(t *testing.T) {
	if !SameSearchTitlePrefix("Tensei shitara Dainana Ouji", "Tensei Shitara Dai Nana Ouji Datta node, Kimamani Majutsu wo Kiwamemasu") {
		t.Fatal("a long title prefix should identify candidates for metadata lookup")
	}
	for _, pair := range [][2]string{
		{"hunter", "City Hunter"},
		{"Tensei Shitara", "Tensei Shitara Dai Nana Ouji"},
		{"Tensei Shitara Dai Nana Ouji", "Reincarnated as a Sword"},
	} {
		if SameSearchTitlePrefix(pair[0], pair[1]) {
			t.Errorf("short or non-prefix terms must not be duplicate discovery keys: %q, %q", pair[0], pair[1])
		}
	}
}

func TestExactCanonicalPrefersPrimaryTitleOverAnotherAnimeSynonym(t *testing.T) {
	main := domain.Anime{Title: "Black Clover", Titles: []string{"Black Clover"}, PrimaryTitles: []string{"Black Clover"}, AniListID: 97940}
	short := domain.Anime{Title: "Mugyutto! Black Clover", Titles: []string{"Mugyutto! Black Clover", "Black Clover"}, PrimaryTitles: []string{"Mugyutto! Black Clover"}, AniListID: 110318}
	item := domain.Anime{Title: "Black Clover"}
	id, _ := exactCanonical(item, []domain.Anime{short, main})
	if id != main.AniListID {
		t.Fatalf("primary title resolved to ambiguous synonym identity %d; want %d", id, main.AniListID)
	}
}

func TestSearchResultRelevanceAllowsStrongTypoOnly(t *testing.T) {
	if !searchResultMatchesQuery("Demon Slyer", domain.Anime{Title: "Demon Slayer"}, nil) {
		t.Fatal("a close one-character typo should remain searchable")
	}
	if !searchResultMatchesQuery("Black Clover", domain.Anime{Title: "Mugyutto! Black Clover"}, nil) {
		t.Fatal("a related title containing the full query should remain searchable")
	}
	for _, sample := range []struct{ query, title string }{
		{query: "Demon Slayer", title: "Onigiri"},
		{query: "Frieren", title: "My Girlfriend's Friend"},
		{query: "cat", title: "Caterpillar"},
	} {
		if searchResultMatchesQuery(sample.query, domain.Anime{Title: sample.title}, nil) {
			t.Errorf("unrelated result %q matched query %q", sample.title, sample.query)
		}
	}
	if searchResultMatchesQuery("cat", domain.Anime{Title: "Caterpillar", AniListID: 50}, []domain.Anime{{Title: "Caterpillar", PrimaryTitles: []string{"Caterpillar"}, AniListID: 50}}) {
		t.Fatal("an AniList substring must not bypass the whole-word relevance check")
	}
}

func TestSearchResultRelevanceIncludesRelatedTitlesWithoutMergingThem(t *testing.T) {
	provider := &fixtureProvider{name: "animefire", items: map[string][]domain.Anime{
		"hunter": {
			{ID: "city-hunter", Provider: "animefire", Title: "City Hunter"},
			{ID: "hunter-movie", Provider: "animefire", Title: "HUNTER×HUNTER: The Last Mission"},
			{ID: "unrelated", Provider: "animefire", Title: "Caterpillar"},
		},
	}}
	result, err := (&Catalog{Providers: []domain.AnimeProvider{provider}}).SearchExpanded(context.Background(), "hunter", 1, nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Items) != 2 {
		t.Fatalf("expected City Hunter and the Hunter x Hunter movie as separate results, got %+v", result.Items)
	}
	want := map[string]bool{"City Hunter": false, "HUNTER×HUNTER: The Last Mission": false}
	for _, item := range result.Items {
		if _, ok := want[item.Title]; ok {
			want[item.Title] = true
		} else {
			t.Errorf("unexpected result %q", item.Title)
		}
	}
	for title, found := range want {
		if !found {
			t.Errorf("related result %q was not returned", title)
		}
	}
}

func TestSearchResultRelevanceMatchesWholeQueryPhrase(t *testing.T) {
	movie := domain.Anime{Title: "HUNTER×HUNTER: The Last Mission", AniListID: 999}
	if !searchResultMatchesQuery("hunter x hunter", movie, []domain.Anime{{Title: "Hunter x Hunter", AniListID: 136}}) {
		t.Fatal("a title containing the complete query phrase should match despite another canonical candidate")
	}
	if searchResultMatchesQuery("hunter x hunter", domain.Anime{Title: "City Hunter"}, nil) {
		t.Fatal("a partial term match must not satisfy a multiword query")
	}
}

func TestTitleSimilarityOnlyRanksAndDoesNotMerge(t *testing.T) {
	p := &fixtureProvider{name: "animefire", items: map[string][]domain.Anime{"Demon Slyer": {{ID: "1", Provider: "animefire", Title: "Demon Slayer"}, {ID: "2", Provider: "animefire", Title: "Demon Slyer"}}}}
	r, err := (&Catalog{Providers: []domain.AnimeProvider{p}}).SearchExpanded(context.Background(), "Demon Slyer", 1, nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(r.Items) != 2 {
		t.Fatalf("fuzzy matches must remain separate; got %d", len(r.Items))
	}
	if r.Items[0].Title != "Demon Slyer" {
		t.Fatalf("exact query match should rank higher: %+v", r.Items)
	}
}

func TestSearchExpandedPreservesPageAndAggregatesHasNext(t *testing.T) {
	p := &fixtureProvider{name: "animefire", hasNext: true, items: map[string][]domain.Anime{"title": {{ID: "1", Provider: "animefire", Title: "Title"}}}}
	r, err := (&Catalog{Providers: []domain.AnimeProvider{p}}).SearchExpanded(context.Background(), "title", 3, nil)
	if err != nil {
		t.Fatal(err)
	}
	if r.Page != 3 || !r.HasNext {
		t.Fatalf("page metadata lost: %+v", r)
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	if len(p.pages) != 1 || p.pages[0] != 3 {
		t.Fatalf("provider received wrong page: %v", p.pages)
	}
}

type waitingProvider struct{ started chan struct{} }

func (p *waitingProvider) Name() string { return "fixture" }
func (p *waitingProvider) Search(ctx context.Context, _ string, _ int) (domain.SearchResult, error) {
	select {
	case p.started <- struct{}{}:
	default:
	}
	<-ctx.Done()
	return domain.SearchResult{}, ctx.Err()
}
func (p *waitingProvider) Details(context.Context, domain.Anime) (domain.Detail, error) {
	return domain.Detail{}, nil
}
func (p *waitingProvider) Resolve(context.Context, domain.Episode) ([]domain.Stream, error) {
	return nil, nil
}

func TestSearchExpandedCancellationStopsPendingProviderJobs(t *testing.T) {
	p := &waitingProvider{started: make(chan struct{}, 1)}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() {
		_, err := (&Catalog{Providers: []domain.AnimeProvider{p}}).SearchExpanded(ctx, "query", 1, nil)
		done <- err
	}()
	select {
	case <-p.started:
	case <-time.After(time.Second):
		t.Fatal("provider search did not start")
	}
	cancel()
	select {
	case err := <-done:
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("got %v, want cancellation", err)
		}
	case <-time.After(time.Second):
		t.Fatal("search did not stop after cancellation")
	}
}

func TestDetailsPreferExplicitSeasonGroupsWithoutMergingEpisodes(t *testing.T) {
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	main := domain.Anime{ID: "fire", Provider: "animefire", Title: "Jujutsu Kaisen", AniListID: 100}
	alternate := domain.Anime{ID: "cc", Provider: "animesonlinecc", Title: "Jujutsu Kaisen"}
	oneSeason := domain.Detail{Anime: main, Episodes: []domain.Episode{{ID: "f1", Provider: "animefire", Season: 1, Number: 1}}}
	threeSeasons := domain.Detail{Anime: alternate, Episodes: []domain.Episode{{ID: "c1", Provider: "animesonlinecc", Season: 1, Number: 1}, {ID: "c2", Provider: "animesonlinecc", Season: 2, Number: 1}, {ID: "c3", Provider: "animesonlinecc", Season: 3, Number: 1}}}
	first := &fixtureProvider{name: "animefire", detail: oneSeason}
	second := &fixtureProvider{name: "animesonlinecc", detail: threeSeasons}
	catalog := &Catalog{Providers: []domain.AnimeProvider{first, second}, Store: db}
	main.Variants = []domain.Anime{alternate}
	detail, err := catalog.Details(context.Background(), main)
	if err != nil {
		t.Fatal(err)
	}
	if len(detail.Episodes) != 3 || detail.Episodes[0].Provider != "animesonlinecc" {
		t.Fatalf("unexpected selected episodes: %+v", detail.Episodes)
	}
	if detail.Episodes[1].Season != 2 || detail.Anime.AniListID != 100 {
		t.Fatalf("season groups or canonical identity lost: %+v", detail)
	}
}
