package providers

import (
	"context"
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/media"
	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/player"
)

// TestLiveProviderPlayerMPVE2E verifies a real provider page all the way through
// media validation, the local gateway, and MPV decoding. It is opt-in because
// public catalogs and media hosts change independently of the application.
func TestLiveProviderPlayerMPVE2E(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE") != "1" || os.Getenv("ANIMECAOS_PLAYER_TEST") != "1" {
		t.Skip("set ANIMECAOS_LIVE=1 and ANIMECAOS_PLAYER_TEST=1 for provider-to-MPV checks")
	}

	providerName := strings.TrimSpace(os.Getenv("ANIMECAOS_LIVE_PROVIDER"))
	query := strings.TrimSpace(os.Getenv("ANIMECAOS_LIVE_QUERY"))
	expected := strings.TrimSpace(os.Getenv("ANIMECAOS_LIVE_EXPECTED"))
	if providerName == "" {
		t.Fatal("set ANIMECAOS_LIVE_PROVIDER to select one source")
	}
	if query == "" {
		switch providerName {
		case "sushianimes", "animesonlinecc":
			query = "Naruto"
		case "otakulogia":
			query = "Hunter x Hunter"
		case "animefire":
			query = "One Piece"
		default:
			t.Fatalf("unknown provider %q", providerName)
		}
	}
	if expected == "" {
		expected = normalized(query)
	}
	episodeNumber := 1.0
	if raw := strings.TrimSpace(os.Getenv("ANIMECAOS_LIVE_EPISODE_NUMBER")); raw != "" {
		parsed, err := strconv.ParseFloat(raw, 64)
		if err != nil || parsed <= 0 {
			t.Fatalf("invalid ANIMECAOS_LIVE_EPISODE_NUMBER %q", raw)
		}
		episodeNumber = parsed
	}

	var provider domain.AnimeProvider
	client := netx.New()
	switch providerName {
	case "animefire":
		provider = NewAnimeFire(client)
	case "sushianimes":
		provider = NewSushiAnimes(client)
	case "animesonlinecc":
		provider = NewOnlineCC(client)
	case "otakulogia":
		provider = NewOtakulogia(client)
	default:
		t.Fatalf("unknown provider %q", providerName)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	result, err := provider.Search(ctx, query, 1)
	if err != nil {
		t.Fatalf("%s search %q: %v", providerName, query, err)
	}
	var selected domain.Anime
	for _, candidate := range result.Items {
		if liveResultMatches(candidate, expected, []string{query}) {
			selected = candidate
			break
		}
	}
	if selected.ID == "" {
		t.Fatalf("%s search %q returned no matching title among %d result(s)", providerName, query, len(result.Items))
	}
	t.Logf("catalog title=%q", selected.Title)

	detail, err := provider.Details(ctx, selected)
	if err != nil {
		t.Fatalf("%s details for %q: %v", providerName, selected.Title, err)
	}
	var episode domain.Episode
	for _, candidate := range detail.Episodes {
		if candidate.Number == episodeNumber && (candidate.Season == 0 || candidate.Season == 1) {
			episode = candidate
			break
		}
	}
	if episode.ID == "" {
		t.Fatalf("%s has no explicit episode %g for %q", providerName, episodeNumber, selected.Title)
	}
	t.Logf("episode season=%d number=%g title=%q", episode.Season, episode.Number, episode.Title)

	streams, err := provider.Resolve(ctx, episode)
	if err != nil {
		t.Fatalf("%s resolve episode %q: %v", providerName, episode.Title, err)
	}
	if len(streams) == 0 {
		t.Fatalf("%s returned no streams for episode %q", providerName, episode.Title)
	}

	var failures []string
	for index, stream := range streams {
		if stream.Kind == "hls" {
			stream, err = media.Best(ctx, stream)
		} else {
			err = media.Validate(ctx, stream)
		}
		if err != nil {
			failures = append(failures, fmt.Sprintf("candidate %d preflight: %v", index+1, err))
			continue
		}
		state, err := liveMPVDecodeAndSeek(ctx, stream, providerName, index+1)
		if err != nil {
			failures = append(failures, fmt.Sprintf("candidate %d MPV: %v", index+1, err))
			continue
		}
		parsed, _ := url.Parse(stream.URL)
		t.Logf("MPV confirmed source=%s host=%s kind=%s audio=%s quality=%v resolution=%dx%d codecs=%s/%s position=%.1fs seek passed",
			providerName, parsed.Hostname(), stream.Kind, stream.Audio, stream.Qualities,
			state.Width, state.Height, state.VideoCodec, state.AudioCodec, state.Position)
		return
	}
	t.Fatalf("%s has no candidate that passes MPV: %s", providerName, strings.Join(failures, "; "))
}

func liveMPVDecodeAndSeek(parent context.Context, stream domain.Stream, provider string, candidate int) (player.State, error) {
	ctx, cancel := context.WithTimeout(parent, 50*time.Second)
	defer cancel()
	gateway, err := media.NewGateway()
	if err != nil {
		return player.State{}, fmt.Errorf("create gateway: %w", err)
	}
	defer gateway.Close()
	localURL, release := gateway.Register(stream)
	defer release()

	events := make(chan player.State, 256)
	controller := player.New(func(state player.State) {
		select {
		case events <- state:
		default:
		}
	})
	defer controller.Close()
	session := fmt.Sprintf("live-%s-%d", provider, candidate)
	if err := controller.Start(ctx, localURL, "mpv", "", 0, session); err != nil {
		return player.State{}, fmt.Errorf("start MPV: %w", err)
	}
	seekTarget := -1.0
	for {
		select {
		case <-ctx.Done():
			return player.State{}, fmt.Errorf("timed out waiting for MPV decode/seek")
		case state := <-events:
			if state.Error != "" {
				return player.State{}, fmt.Errorf("MPV: %s", state.Error)
			}
			if !state.Playing {
				if state.EOF && seekTarget >= 0 {
					return state, nil
				}
				return player.State{}, fmt.Errorf("MPV ended before decode and seek: %+v", state)
			}
			if seekTarget < 0 && state.Position > 2 && state.Duration > 15 &&
				state.VideoCodec != "" && state.AudioCodec != "" && state.Width > 0 && state.Height > 0 {
				seekTarget = min(10, state.Duration-3)
				if err := controller.Command("seek", seekTarget); err != nil {
					return player.State{}, fmt.Errorf("seek MPV: %w", err)
				}
			}
			if seekTarget >= 0 && state.Position >= seekTarget+1 && state.VideoCodec != "" && state.AudioCodec != "" {
				return state, nil
			}
		}
	}
}
