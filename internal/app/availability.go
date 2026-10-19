package app

import (
	"context"
	"fmt"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/media"
)

var availabilitySourceTimeout = 12 * time.Second

var qualityHeightPattern = regexp.MustCompile(`(?i)(\d{3,4})\s*p`)

type availabilityJob struct {
	index           int
	source          domain.Anime
	requestedSeason int
}

type availabilityResult struct {
	index  int
	source string
	height int
	valid  bool
}

func (s *Service) verifySearchAvailability(ctx context.Context, result domain.SearchResult, requestedSeasons ...int) domain.SearchResult {
	requestedSeason := 0
	if len(requestedSeasons) > 0 && requestedSeasons[0] > 0 {
		requestedSeason = requestedSeasons[0]
	}
	sampleEpisode := sampleEpisodeLabel(requestedSeason)
	type itemState struct {
		anime    domain.Anime
		checked  int
		total    int
		verified map[string]bool
	}
	states := make([]itemState, len(result.Items))
	jobs := make([]availabilityJob, 0, len(result.Items)*2)
	visible := make([]bool, len(result.Items))

	for i, anime := range result.Items {
		anime.Availability = nil
		states[i] = itemState{anime: anime, verified: map[string]bool{}}
		if cached, ok := s.cachedAvailability(anime, requestedSeason); ok {
			if cached.available {
				states[i].anime.Availability = &cached.availability
				promoteSearchGroup(&states[i].anime)
				visible[i] = true
			}
			states[i].total = 0
			continue
		}
		sources := uniqueAnimeSources(anime)
		states[i].total = len(sources)
		for _, source := range sources {
			jobs = append(jobs, availabilityJob{index: i, source: source, requestedSeason: requestedSeason})
		}
	}
	if len(jobs) == 0 {
		filtered := make([]domain.Anime, 0, len(result.Items))
		for i := range states {
			if visible[i] {
				filtered = append(filtered, states[i].anime)
			}
		}
		result.Items = filtered
		return result
	}

	workers := min(6, len(jobs))
	results := make(chan availabilityResult, len(jobs))
	var wg sync.WaitGroup
	providerJobs := make(map[string][]availabilityJob)
	for _, job := range jobs {
		providerJobs[job.source.Provider] = append(providerJobs[job.source.Provider], job)
	}
	providerNames := make([]string, 0, len(providerJobs))
	for providerName := range providerJobs {
		providerNames = append(providerNames, providerName)
	}
	sort.Strings(providerNames)
	globalLimit := make(chan struct{}, workers)
	for _, providerName := range providerNames {
		queue := make(chan availabilityJob, len(providerJobs[providerName]))
		for _, job := range providerJobs[providerName] {
			queue <- job
		}
		close(queue)
		for i := 0; i < min(2, len(providerJobs[providerName])); i++ {
			wg.Add(1)
			go func(queue <-chan availabilityJob) {
				defer wg.Done()
				for job := range queue {
					select {
					case globalLimit <- struct{}{}:
					case <-ctx.Done():
						return
					}
					height, valid := s.verifySource(ctx, job.source, job.requestedSeason)
					<-globalLimit
					results <- availabilityResult{index: job.index, source: job.source.Provider, height: height, valid: valid}
				}
			}(queue)
		}
	}
	go func() { wg.Wait(); close(results) }()

	recordCheck := func(check availabilityResult) {
		state := &states[check.index]
		state.checked++
		if check.valid && check.source != "" {
			state.verified[check.source] = true
			availability := state.anime.Availability
			if availability == nil {
				availability = &domain.PlaybackAvailability{SampleEpisode: sampleEpisode}
				state.anime.Availability = availability
			}
			if check.height > availability.MaxHeight {
				availability.MaxHeight = check.height
				availability.Quality = fmt.Sprintf("Até %dp", check.height)
			} else if availability.MaxHeight == 0 {
				availability.Quality = "Qualidade não identificada"
			}
			availability.SourcesVerified = sortedKeys(state.verified)
			visible[check.index] = true
		}
	}
	for {
		select {
		case check, ok := <-results:
			if !ok {
				goto checksComplete
			}
			if ctx.Err() == nil || check.valid {
				// verifySource rejects a result if its context expired, so a valid
				// completion can still be retained when it reached this channel just
				// as the page deadline fired.
				recordCheck(check)
			}
		case <-ctx.Done():
			// Workers send to a buffer sized for every job. Drain completions
			// already available, then return without waiting for slow browser or
			// provider cleanup. No source can become valid after its context ends.
			for {
				select {
				case check, ok := <-results:
					if !ok {
						goto checksComplete
					}
					if check.valid {
						recordCheck(check)
					}
				default:
					goto checksComplete
				}
			}
		}
	}

checksComplete:

	filtered := make([]domain.Anime, 0, len(result.Items))
	for i := range states {
		state := &states[i]
		// A page-level deadline limits how many sources can be checked, but it
		// must not discard cards whose preflight already succeeded. Incomplete
		// candidates remain hidden because visible is set only by a valid source
		// (or a positive cache entry).
		if visible[i] {
			promoteSearchGroup(&state.anime)
		}
		if state.checked >= state.total {
			availability := domain.PlaybackAvailability{SampleEpisode: sampleEpisode}
			if state.anime.Availability != nil {
				availability = *state.anime.Availability
			}
			s.cacheAvailability(state.anime, requestedSeason, availability, visible[i])
		}
		if visible[i] {
			filtered = append(filtered, state.anime)
		}
	}
	result.Items = filtered
	return result
}

func promoteSearchGroup(anime *domain.Anime) {
	if anime.SearchGroupID > 0 {
		anime.AniListID = anime.SearchGroupID
		anime.SearchGroupID = 0
	}
}

func (s *Service) verifySource(parent context.Context, anime domain.Anime, requestedSeason int) (int, bool) {
	ctx, cancel := context.WithTimeout(parent, availabilitySourceTimeout)
	defer cancel()
	provider, err := s.catalog.Provider(anime.Provider)
	if err != nil {
		return 0, false
	}
	detail, err := provider.Details(ctx, anime)
	if err != nil || ctx.Err() != nil {
		return 0, false
	}
	episode, ok := firstEpisodeForSeason(detail.Episodes, requestedSeason)
	if !ok {
		return 0, false
	}
	streams, err := provider.Resolve(ctx, episode)
	if err != nil || ctx.Err() != nil {
		return 0, false
	}
	bestHeight := 0
	valid := false
	for _, stream := range streams {
		if ctx.Err() != nil {
			break
		}
		stream.Source = anime.Provider
		if stream.Kind == "hls" {
			stream, err = media.Best(ctx, stream)
		} else {
			err = media.Validate(ctx, stream)
			if err == nil {
				if info, inspectErr := media.Inspect(ctx, stream); inspectErr == nil {
					if info.AudioCodec == "" {
						continue
					}
					if info.Height > 0 {
						stream.Height = info.Height
					}
					if info.Bitrate > 0 {
						stream.Bandwidth = info.Bitrate
					}
				}
			}
		}
		if err != nil {
			continue
		}
		valid = true
		height := max(stream.Height, streamQualityHeight(stream))
		bestHeight = max(bestHeight, height)
	}
	if ctx.Err() != nil {
		return 0, false
	}
	return bestHeight, valid
}

func firstEpisode(episodes []domain.Episode) (domain.Episode, bool) {
	return firstEpisodeForSeason(episodes, 0)
}

func firstEpisodeForSeason(episodes []domain.Episode, requestedSeason int) (domain.Episode, bool) {
	if requestedSeason > 1 {
		var matches []domain.Episode
		for _, episode := range episodes {
			if episode.Number == 1 && episode.Season == requestedSeason {
				matches = append(matches, episode)
			}
		}
		if len(matches) != 1 {
			return domain.Episode{}, false
		}
		return matches[0], true
	}
	var explicitSeason []domain.Episode
	var unspecifiedSeason []domain.Episode
	for _, episode := range episodes {
		if episode.Number != 1 {
			continue
		}
		switch episode.Season {
		case 1:
			explicitSeason = append(explicitSeason, episode)
		case 0:
			unspecifiedSeason = append(unspecifiedSeason, episode)
		}
	}
	matches := explicitSeason
	if len(matches) == 0 {
		matches = unspecifiedSeason
	}
	if len(matches) != 1 {
		return domain.Episode{}, false
	}
	return matches[0], true
}

func sampleEpisodeLabel(season int) string {
	if season > 1 {
		return fmt.Sprintf("T%d E1", season)
	}
	return "E1"
}

func uniqueAnimeSources(anime domain.Anime) []domain.Anime {
	sources := make([]domain.Anime, 0, len(anime.Variants)+1)
	seen := map[string]bool{}
	for _, source := range append([]domain.Anime{anime}, anime.Variants...) {
		if source.Provider == "" || source.ID == "" || seen[source.Key()] {
			continue
		}
		seen[source.Key()] = true
		sources = append(sources, source)
	}
	return sources
}

func streamQualityHeight(stream domain.Stream) int {
	height := stream.Height
	for _, quality := range stream.Qualities {
		match := qualityHeightPattern.FindStringSubmatch(quality)
		if len(match) != 2 {
			continue
		}
		var value int
		fmt.Sscanf(match[1], "%d", &value)
		height = max(height, value)
	}
	return height
}

func sortedKeys(values map[string]bool) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func availabilityKey(anime domain.Anime, requestedSeason int) string {
	identityID := anime.AniListID
	if identityID == 0 {
		identityID = anime.SearchGroupID
	}
	key := ""
	if identityID > 0 {
		key = fmt.Sprintf("anilist:%d", identityID)
	} else {
		key = anime.Key()
	}
	return fmt.Sprintf("%s:season:%d", key, requestedSeason)
}

func (s *Service) cachedAvailability(anime domain.Anime, requestedSeason int) (availabilityCacheEntry, bool) {
	s.availabilityMu.Lock()
	defer s.availabilityMu.Unlock()
	entry, ok := s.availabilityCache[availabilityKey(anime, requestedSeason)]
	if !ok || time.Now().After(entry.expires) {
		delete(s.availabilityCache, availabilityKey(anime, requestedSeason))
		return availabilityCacheEntry{}, false
	}
	return entry, true
}

func (s *Service) cacheAvailability(anime domain.Anime, requestedSeason int, availability domain.PlaybackAvailability, available bool) {
	ttl := 20 * time.Second
	if available {
		ttl = 2 * time.Minute
	}
	s.availabilityMu.Lock()
	defer s.availabilityMu.Unlock()
	if s.availabilityCache == nil {
		s.availabilityCache = map[string]availabilityCacheEntry{}
	}
	if len(s.availabilityCache) > 500 {
		for key, entry := range s.availabilityCache {
			if time.Now().After(entry.expires) {
				delete(s.availabilityCache, key)
			}
		}
	}
	s.availabilityCache[availabilityKey(anime, requestedSeason)] = availabilityCacheEntry{availability: availability, available: available, expires: time.Now().Add(ttl)}
}

func betterStream(left, right domain.Stream, preferredAudio string) bool {
	leftAudio, rightAudio := audioRank(left.Audio, preferredAudio), audioRank(right.Audio, preferredAudio)
	if leftAudio != rightAudio {
		return leftAudio < rightAudio
	}
	leftHeight, rightHeight := streamQualityHeight(left), streamQualityHeight(right)
	if leftHeight != rightHeight {
		return leftHeight > rightHeight
	}
	return left.Bandwidth > right.Bandwidth
}

func audioRank(audio, preferred string) int {
	preferred = strings.ToLower(strings.TrimSpace(preferred))
	audio = strings.ToLower(strings.TrimSpace(audio))
	if preferred == "" || audio == preferred {
		return 0
	}
	if strings.Contains(audio, preferred) {
		return 1
	}
	return 2
}
