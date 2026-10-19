package providers

import (
	"strings"
	"testing"

	"github.com/PuerkitoBio/goquery"
)

func TestPagePlayerCandidatesIgnoresFramesOutsidePlayerAndAdWrappers(t *testing.T) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(`
		<div class="player-container">
			<iframe src="https://embed.example/player/1" referrerpolicy="no-referrer"></iframe>
			<div class="ad-banner"><iframe src="https://ads.example/banner"></iframe></div>
		</div>
		<iframe src="https://tags.crwdcntrl.net/tracker"></iframe>
	`))
	if err != nil {
		t.Fatal(err)
	}
	got := pagePlayerCandidates(doc, "https://anime.example/episode/1")
	if len(got) != 1 || got[0].URL != "https://embed.example/player/1" || got[0].ReferrerPolicy != "no-referrer" {
		t.Fatalf("unexpected player candidates: %+v", got)
	}
}

func TestPagePlayerCandidatesDoesNotFallBackToPageWideFrames(t *testing.T) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(`
		<div class="player-container"></div>
		<iframe src="https://t.dtscout.com/tracker"></iframe>
		<iframe src="https://unrelated.example/frame"></iframe>
	`))
	if err != nil {
		t.Fatal(err)
	}
	if got := pagePlayerCandidates(doc, "https://anime.example/episode/1"); len(got) != 0 {
		t.Fatalf("page-wide frames escaped an empty player root: %+v", got)
	}
}

func TestPagePlayerCandidatesUsesSemanticFrameWhenNoPlayerRootExists(t *testing.T) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(`
		<iframe class="episode-player" src="https://embed.example/episode"></iframe>
		<iframe src="https://unknown-tracker.example/pixel"></iframe>
	`))
	if err != nil {
		t.Fatal(err)
	}
	got := pagePlayerCandidates(doc, "https://anime.example/episode/1")
	if len(got) != 1 || got[0].URL != "https://embed.example/episode" {
		t.Fatalf("semantic player was not isolated from unrelated frame: %+v", got)
	}
}

func TestAdvertisingURLUsesHostBoundaries(t *testing.T) {
	for _, raw := range []string{
		"https://t.dtscout.com/track",
		"https://tags.crwdcntrl.net/segment",
		"https://sub.doubleclick.net/ad.js",
	} {
		if !isAdvertisingURL(raw) {
			t.Errorf("known tracker was not blocked: %s", raw)
		}
	}
	for _, raw := range []string{
		"https://video.example/episode.m3u8",
		"https://notdoubleclick.net/episode.mp4",
		"https://player.example/embed/1?next=https://doubleclick.net/ad",
	} {
		if isAdvertisingURL(raw) {
			t.Errorf("legitimate player URL was falsely blocked: %s", raw)
		}
	}
}
