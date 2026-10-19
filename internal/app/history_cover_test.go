package app

import (
	"testing"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/store"
)

func TestPreviewTitleCandidatesKeepExactAndRecoverLegacyVariant(t *testing.T) {
	got := previewTitleCandidates("Bleach: Sennen Kessen-hen - Ketsubetsu-tan (Dublado)")
	want := []string{
		"Bleach: Sennen Kessen-hen - Ketsubetsu-tan (Dublado)",
		"Bleach: Sennen Kessen-hen - Ketsubetsu-tan",
		"Bleach: Sennen Kessen-hen",
	}
	if len(got) != len(want) {
		t.Fatalf("got %#v, want %#v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("candidate %d = %q, want %q", i, got[i], want[i])
		}
	}
}

func TestPreviewTitleCandidatesExpandKnownLegacyNames(t *testing.T) {
	cases := map[string]string{
		"Naruto Clássico Dublado": "Naruto",
		"Dogulwang":               "Tomb Raider King",
		"Yuu☆Yuu☆Hakusho":         "Yu Yu Hakusho",
	}
	for title, expected := range cases {
		found := false
		for _, candidate := range previewTitleCandidates(title) {
			if candidate == expected {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("%q candidates %#v do not include %q", title, previewTitleCandidates(title), expected)
		}
	}
}

func TestSaveHistoryCoverPersistsRecoveredPoster(t *testing.T) {
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	h := domain.History{Anime: domain.Anime{ID: "legacy-title", Provider: "legacy", Title: "Legacy title"}, NeedsResolve: true}
	if err := db.Put("history", h.Anime.Key(), h); err != nil {
		t.Fatal(err)
	}
	s := &Service{db: db}
	if err := s.SaveHistoryCover(h.Anime.Key(), "https://images.example/poster.jpg"); err != nil {
		t.Fatal(err)
	}
	var persisted domain.History
	if err := db.Get("history", h.Anime.Key(), &persisted); err != nil {
		t.Fatal(err)
	}
	if persisted.Anime.Cover != "https://images.example/poster.jpg" {
		t.Fatalf("cover was not persisted: %+v", persisted.Anime)
	}
}
