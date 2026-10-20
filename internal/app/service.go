// Package app is the shared application layer used by Wails and the CLI.
package app

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/downloads"
	"github.com/henriqqw/animecaos/internal/integrations"
	"github.com/henriqqw/animecaos/internal/manga"
	"github.com/henriqqw/animecaos/internal/media"
	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/platform"
	"github.com/henriqqw/animecaos/internal/player"
	"github.com/henriqqw/animecaos/internal/providers"
	"github.com/henriqqw/animecaos/internal/store"
	"github.com/henriqqw/animecaos/internal/update"
)

type operation struct {
	cancel context.CancelFunc
	token  string
}
type playback struct {
	ID                string
	Anime             domain.Anime
	Episodes          []domain.Episode
	Index             int
	Release           func()
	Saved             time.Time
	Finished          bool
	Request           uint64
	Local             bool
	FallbackRemaining int
	StartPosition     float64
	Source            string
	Height            int
	Bandwidth         int
}
type Service struct {
	ctx               context.Context
	cancel            context.CancelFunc
	mu                sync.Mutex
	playMu            sync.Mutex
	playRequest       uint64
	ops               map[string]operation
	settings          domain.Settings
	current           playback
	emit              func(string, any)
	db                *store.Store
	catalog           *providers.Catalog
	metadata          *integrations.Metadata
	accounts          *integrations.Accounts
	discord           *integrations.Discord
	manga             *manga.Service
	gateway           *media.Gateway
	player            playerController
	queue             *downloads.Queue
	updater           *update.Service
	bookRelease       func()
	imageSlots        chan struct{}
	availabilityMu    sync.Mutex
	availabilityCache map[string]availabilityCacheEntry
}

type availabilityCacheEntry struct {
	availability domain.PlaybackAvailability
	available    bool
	expires      time.Time
}

type playerController interface {
	Start(context.Context, string, string, string, float64, string) error
	Stop()
	Close()
	State() player.State
	Command(string, float64) error
}

type Initial struct {
	Settings domain.Settings        `json:"settings"`
	Version  string                 `json:"version"`
	Accounts []integrations.Account `json:"accounts"`
}
type PlayerEvent struct {
	State   player.State   `json:"state"`
	Anime   domain.Anime   `json:"anime"`
	Episode domain.Episode `json:"episode"`
}
type Diagnosis struct {
	Platform     string            `json:"platform"`
	DataDir      string            `json:"dataDir"`
	Dependencies map[string]string `json:"dependencies"`
	Discord      bool              `json:"discord"`
}

func New(parent context.Context, dir string, emit func(string, any)) (*Service, error) {
	db, e := store.Open(dir)
	if e != nil {
		return nil, e
	}
	g, e := media.NewGateway()
	if e != nil {
		db.Close()
		return nil, e
	}
	ctx, cancel := context.WithCancel(parent)
	if emit == nil {
		emit = func(string, any) {}
	}
	c := netx.New()
	s := &Service{ctx: ctx, cancel: cancel, ops: map[string]operation{}, db: db, gateway: g, emit: emit, settings: db.Defaults(), discord: &integrations.Discord{}, imageSlots: make(chan struct{}, 3), availabilityCache: map[string]availabilityCacheEntry{}}
	s.catalog = &providers.Catalog{Providers: []domain.AnimeProvider{providers.NewAnimeFire(c), providers.NewSushiAnimes(c), providers.NewOnlineCC(c), providers.NewOtakulogia(c)}, Store: db}
	s.metadata = integrations.NewMetadata(c, db)
	s.accounts = integrations.NewAccounts(db, s.metadata)
	s.manga = manga.New(c)
	s.updater = update.New(c)
	s.player = player.New(s.onPlayer)
	s.discord.Configure(s.settings.Discord)
	s.queue = downloads.New(db, g, s.resolve, s.settings.DownloadsDir, s.settings.Concurrent, func(d domain.Download) { emit("download", d) })
	s.queue.SetStreamClient(c.Stream)
	s.queue.SetMangaDownloader(s.manga.Download)
	return s, nil
}
func (s *Service) Close() {
	s.cancel()
	s.player.Close()
	s.queue.Close()
	s.discord.Close()
	s.metadata.Close()
	s.gateway.Close()
	s.db.Close()
}
func (s *Service) operation(id string, timeout time.Duration) (context.Context, func()) {
	ctx, cancel := context.WithTimeout(s.ctx, timeout)
	token := media.ID()
	s.mu.Lock()
	if old, ok := s.ops[id]; ok {
		old.cancel()
	}
	s.ops[id] = operation{cancel, token}
	s.mu.Unlock()
	return ctx, func() {
		cancel()
		s.mu.Lock()
		if o, ok := s.ops[id]; ok && o.token == token {
			delete(s.ops, id)
		}
		s.mu.Unlock()
	}
}
func (s *Service) Cancel(id string) {
	s.mu.Lock()
	if op, ok := s.ops[id]; ok {
		op.cancel()
		delete(s.ops, id)
	}
	s.mu.Unlock()
}
func (s *Service) Settings() domain.Settings { s.mu.Lock(); defer s.mu.Unlock(); return s.settings }
func (s *Service) Initial() Initial {
	return Initial{Settings: s.Settings(), Version: update.Version, Accounts: s.accounts.Profiles()}
}
func (s *Service) SaveSettings(v domain.Settings) error {
	if v.Theme != "system" && v.Theme != "light" && v.Theme != "dark" {
		return fmt.Errorf("tema inválido")
	}
	if v.UIScale < 1 || v.UIScale > 1.5 {
		return fmt.Errorf("escala deve ficar entre 1 e 1,5")
	}
	if v.Concurrent < 1 || v.Concurrent > 5 {
		return fmt.Errorf("downloads simultâneos: 1 a 5")
	}
	if v.PlayerMode != "mpv" && v.PlayerMode != "custom" && v.PlayerMode != "system" {
		return fmt.Errorf("player inválido")
	}
	if !filepath.IsAbs(v.DownloadsDir) {
		return fmt.Errorf("escolha uma pasta absoluta para downloads")
	}
	if v.AutoCloseMS < 0 || v.AutoCloseMS > 60000 {
		return fmt.Errorf("tempo de fechamento inválido")
	}
	if e := os.MkdirAll(v.DownloadsDir, 0755); e != nil {
		return e
	}
	if e := s.db.Put("settings", "app", v); e != nil {
		return e
	}
	s.mu.Lock()
	s.settings = v
	s.mu.Unlock()
	s.queue.Configure(v.DownloadsDir, v.Concurrent)
	s.discord.Configure(v.Discord)
	return nil
}
func (s *Service) Search(id, q string, page int, preferred *domain.Anime) (domain.SearchResult, error) {
	ctx, end := s.operation(id, 35*time.Second)
	defer end()
	discoveryCtx, cancelDiscovery := context.WithTimeout(ctx, 15*time.Second)
	result, err := s.searchCandidates(discoveryCtx, q, page, preferred)
	discoveryTimedOut := errors.Is(discoveryCtx.Err(), context.DeadlineExceeded)
	cancelDiscovery()
	if ctx.Err() != nil {
		return result, ctx.Err()
	}
	if err != nil && !discoveryTimedOut {
		return result, err
	}
	if discoveryTimedOut {
		result.Warnings = appendUniqueWarning(result.Warnings, "A busca atingiu o limite de tempo; alguns resultados podem estar incompletos.")
		if len(result.Items) == 0 {
			return result, nil
		}
	}
	intent := providers.InferSearchIntent(q)
	preflightCtx, cancelPreflight := context.WithTimeout(ctx, 12*time.Second)
	verified := s.verifySearchAvailability(preflightCtx, result, intent.Season)
	preflightTimedOut := errors.Is(preflightCtx.Err(), context.DeadlineExceeded)
	cancelPreflight()
	if ctx.Err() != nil {
		return verified, ctx.Err()
	}
	if preflightTimedOut {
		verified.Warnings = appendUniqueWarning(verified.Warnings, "A validação atingiu o limite de tempo; alguns resultados podem estar incompletos.")
	}
	return verified, nil
}

func appendUniqueWarning(warnings []string, warning string) []string {
	for _, current := range warnings {
		if current == warning {
			return warnings
		}
	}
	return append(warnings, warning)
}

func (s *Service) searchCandidates(ctx context.Context, q string, page int, preferred *domain.Anime) (domain.SearchResult, error) {
	var matches []domain.Anime
	if preferred != nil && preferred.AniListID > 0 {
		matches, _ = s.metadata.TitleMatches(ctx, q, preferred.AniListID)
	} else if strings.TrimSpace(q) != "" {
		matches, _ = s.metadata.TitleMatches(ctx, q, 0)
	}
	if len(matches) > 0 {
		result, err := s.catalog.SearchExpanded(ctx, q, page, matches)
		if err != nil {
			return result, err
		}
		return s.resolveDuplicateSearchIdentities(ctx, result), nil
	}
	// Some regional titles are used by a provider but are absent from AniList's
	// search index. Search the provider title first, then resolve its other
	// published names through AniList and retry the expanded catalog query.
	initial, err := s.catalog.SearchExpanded(ctx, q, page, nil)
	if err != nil || len(initial.Items) == 0 {
		return initial, err
	}
	seen := map[string]bool{}
	for _, item := range initial.Items[:min(3, len(initial.Items))] {
		// A metadata lookup on an unrelated first-page result can otherwise
		// assign its AniList identity to the user's query (for example, Onigiri
		// appearing for Demon Slayer when a provider search endpoint is noisy).
		if item.MatchScore < 0.72 {
			continue
		}
		for _, title := range append([]string{item.Title}, item.Titles...) {
			title = strings.TrimSpace(title)
			key := strings.ToLower(title)
			if title == "" || seen[key] {
				continue
			}
			seen[key] = true
			candidates, lookupErr := s.metadata.TitleMatches(ctx, title, 0)
			if lookupErr != nil {
				continue
			}
			for _, candidate := range candidates {
				if providers.SameTitle(item, candidate) {
					matches = append(matches, candidate)
				}
			}
			if len(matches) > 0 {
				result, searchErr := s.catalog.SearchExpanded(ctx, q, page, matches)
				if searchErr != nil {
					return result, searchErr
				}
				return s.resolveDuplicateSearchIdentities(ctx, result), nil
			}
		}
	}
	if ctx.Err() != nil {
		return initial, ctx.Err()
	}
	return s.resolveDuplicateSearchIdentities(ctx, initial), nil
}

func (s *Service) resolveDuplicateSearchIdentities(ctx context.Context, result domain.SearchResult) domain.SearchResult {
	duplicateTitles := []string{}
	queries := []string{}
	querySeen := map[string]bool{}
	for i := range result.Items {
		for j := i + 1; j < len(result.Items); j++ {
			left, right := result.Items[i], result.Items[j]
			if !providers.SameTitle(domain.Anime{Title: left.Title, Titles: left.Titles}, domain.Anime{Title: right.Title, Titles: right.Titles}) &&
				!providers.SameSearchTitlePrefix(left.Title, right.Title) {
				continue
			}
			duplicateTitles = append(duplicateTitles, left.Title, right.Title)
			if (left.AniListID > 0 || left.SearchGroupID > 0) && (right.AniListID > 0 || right.SearchGroupID > 0) {
				continue
			}
			for _, item := range []domain.Anime{left, right} {
				for _, title := range append([]string{item.Title}, item.Titles...) {
					query := leadingTitleWords(title, 5)
					key := strings.ToLower(strings.TrimSpace(query))
					if query != "" && !querySeen[key] && len(queries) < 16 {
						querySeen[key] = true
						queries = append(queries, query)
					}
				}
			}
		}
	}
	if len(queries) == 0 || ctx.Err() != nil {
		return result
	}
	lookups, err := s.metadata.TitleMatchesBatch(ctx, queries)
	if err != nil {
		return result
	}
	metadata := []domain.Anime{}
	seenIDs := map[int]bool{}
	for _, matches := range lookups {
		for _, match := range matches {
			if match.AniListID > 0 && !seenIDs[match.AniListID] {
				seenIDs[match.AniListID] = true
				metadata = append(metadata, match)
			}
		}
	}
	if len(metadata) == 0 {
		return result
	}
	return s.catalog.CanonicalizeDuplicateTitles(result, metadata, duplicateTitles)
}

func leadingTitleWords(title string, count int) string {
	words := strings.Fields(strings.TrimSpace(title))
	if len(words) > count {
		words = words[:count]
	}
	return strings.Join(words, " ")
}
func (s *Service) Discover(id string) (integrations.Discovery, error) {
	ctx, end := s.operation(id, 30*time.Second)
	defer end()
	d, err := s.metadata.Discover(ctx)
	if err != nil {
		return d, err
	}
	// Only the rotating spotlight needs a full synopsis. Translate those in
	// parallel so the home page stays responsive without issuing a request for
	// every card in both discovery shelves.
	var wg sync.WaitGroup
	for i := 0; i < min(5, len(d.Trending)); i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			d.Trending[i].Description = s.metadata.Translate(ctx, d.Trending[i].Description)
		}(i)
	}
	wg.Wait()
	return d, nil
}
func (s *Service) Details(id string, a domain.Anime) (domain.Detail, error) {
	ctx, end := s.operation(id, 35*time.Second)
	defer end()
	return s.catalog.Details(ctx, a)
}
func (s *Service) Preview(id, title string, preferredAniListID int) (domain.Anime, error) {
	ctx, end := s.operation(id, 30*time.Second)
	defer end()
	if preferredAniListID > 0 {
		matches, err := s.metadata.TitleMatches(ctx, title, preferredAniListID)
		if err != nil {
			return domain.Anime{}, err
		}
		if len(matches) == 0 {
			return domain.Anime{}, fmt.Errorf("metadados do anime não encontrados")
		}
		anime := matches[0]
		anime.Description = s.metadata.Translate(ctx, anime.Description)
		return anime, nil
	}
	var lastErr error
	var lastAnime domain.Anime
	for _, query := range previewTitleCandidates(title) {
		a, e := s.metadata.Lookup(ctx, query)
		if e != nil {
			lastErr = e
			continue
		}
		lastAnime = a
		if a.Cover == "" {
			continue
		}
		a.Description = s.metadata.Translate(ctx, a.Description)
		return a, nil
	}
	if lastErr != nil {
		return domain.Anime{}, lastErr
	}
	return lastAnime, nil
}

var previewAudioSuffix = regexp.MustCompile(`(?i)(?:\s*\((?:dublado|legendado|dub|sub)\)|\s+(?:cl[áa]ssico\s+)?(?:dublado|legendado|dub|sub))\s*$`)

var legacyArtworkAliases = map[string][]string{
	"dogulwang":       {"Dogul Wang", "Tomb Raider King"},
	"yuu☆yuu☆hakusho": {"Yuu Yuu Hakusho", "Yu Yu Hakusho"},
}

// previewTitleCandidates only broadens artwork lookups. It never changes the
// anime or episode identity used by the catalog/player.
func previewTitleCandidates(title string) []string {
	title = strings.TrimSpace(title)
	if title == "" {
		return nil
	}
	seen := map[string]bool{}
	out := []string{}
	add := func(value string) {
		value = strings.TrimSpace(value)
		key := strings.ToLower(value)
		if value != "" && !seen[key] {
			seen[key] = true
			out = append(out, value)
		}
	}
	add(title)
	base := previewAudioSuffix.ReplaceAllString(title, "")
	add(base)
	if i := strings.Index(base, " - "); i > 0 {
		add(base[:i])
	}
	plain := strings.NewReplacer("☆", " ", "★", " ", "・", " ").Replace(base)
	plain = strings.Join(strings.Fields(plain), " ")
	add(plain)
	for _, alias := range legacyArtworkAliases[strings.ToLower(strings.TrimSpace(base))] {
		add(alias)
	}
	return out
}

// SaveHistoryCover persists a recovered poster so legacy users do not have to
// repeat title lookups on every app launch.
func (s *Service) SaveHistoryCover(key, cover string) error {
	if strings.TrimSpace(cover) == "" {
		return nil
	}
	var h domain.History
	if err := s.db.Get("history", key, &h); err != nil {
		return err
	}
	if h.Anime.Cover != cover {
		h.Anime.Cover = cover
		if err := s.db.Put("history", key, h); err != nil {
			return err
		}
	}
	return nil
}
func (s *Service) Library() ([]domain.Anime, error) {
	return store.DecodeList[domain.Anime](s.db, "watchlist")
}
func (s *Service) Favorite(a domain.Anime, enabled bool) error {
	if enabled {
		a.Availability = nil
		return s.db.Put("watchlist", a.Key(), a)
	}
	return s.db.Delete("watchlist", a.Key())
}
func (s *Service) History() ([]domain.History, error) {
	history, err := store.DecodeList[domain.History](s.db, "history")
	if err != nil {
		return nil, err
	}
	byAnime := make(map[string]domain.History, len(history))
	for _, item := range history {
		byAnime[item.Anime.Key()] = item
	}
	for _, item := range history {
		if item.Anime.Provider != "local" {
			continue
		}
		localKey := item.Anime.Key()
		path := item.Episode.URL
		if path == "" {
			path = item.Anime.ID
		}
		download, ok := s.completedDownload(path)
		if !ok {
			continue
		}

		key := download.Anime.Key()
		current, exists := byAnime[key]
		if !exists || item.Updated > current.Updated {
			item.Anime = download.Anime
			item.Episode = download.Episode
			if info, err := os.Stat(path); err == nil && info.Mode().IsRegular() {
				item.Episode = localEpisode(download, path)
			}
			item.NeedsResolve = false
			if err := s.db.Put("history", key, item); err != nil {
				return nil, err
			}
			byAnime[key] = item
		}
		if err := s.db.Delete("history", localKey); err != nil {
			return nil, err
		}
	}
	return store.DecodeList[domain.History](s.db, "history")
}
func (s *Service) RemoveHistory(key string) error { return s.db.Delete("history", key) }
func (s *Service) Resume(id, key string) error {
	var h domain.History
	if e := s.db.Get("history", key, &h); e != nil {
		return e
	}
	if h.Anime.Provider == "local" || h.Episode.Provider == "local" {
		path := h.Episode.URL
		if path == "" {
			path = h.Anime.ID
		}
		return s.PlayLocal(path)
	}
	if h.NeedsResolve {
		return fmt.Errorf("confirme o episódio do histórico antigo na lista de episódios")
	}
	d, e := s.Details(id, h.Anime)
	if e != nil {
		return e
	}
	for i, ep := range d.Episodes {
		if ep.Key() == h.Episode.Key() {
			return s.Play(id, d.Anime, d.Episodes, i, true)
		}
	}
	return fmt.Errorf("o episódio salvo não está mais disponível; escolha outro na lista")
}
func (s *Service) resolve(ctx context.Context, a domain.Anime, ep domain.Episode) (domain.Stream, error) {
	streams, err := s.resolveCandidates(ctx, a, ep)
	if err != nil {
		return domain.Stream{}, err
	}
	if len(streams) == 0 {
		return domain.Stream{}, fmt.Errorf("nenhuma fonte de vídeo disponível para este episódio")
	}
	return streams[0], nil
}

func (s *Service) resolveCandidates(ctx context.Context, a domain.Anime, ep domain.Episode) ([]domain.Stream, error) {
	streams, err := s.catalog.ResolveCandidates(ctx, a, ep, s.Settings().Audio)
	if err != nil {
		return nil, err
	}
	var lastErr error
	var valid []domain.Stream
	for _, stream := range streams {
		if stream.Kind == "hls" {
			best, resolveErr := media.Best(ctx, stream)
			if resolveErr == nil {
				valid = append(valid, best)
				continue
			}
			lastErr = resolveErr
			continue
		}
		if validateErr := media.Validate(ctx, stream); validateErr == nil {
			if info, inspectErr := media.Inspect(ctx, stream); inspectErr == nil {
				if info.AudioCodec == "" {
					lastErr = fmt.Errorf("o arquivo de vídeo não contém faixa de áudio")
					continue
				}
				if info.Height > 0 {
					stream.Height = info.Height
				}
				if info.Bitrate > 0 {
					stream.Bandwidth = info.Bitrate
				}
			}
			stream.Height = max(stream.Height, streamQualityHeight(stream))
			valid = append(valid, stream)
		} else {
			lastErr = validateErr
		}
	}
	if len(valid) > 0 {
		preferred := s.Settings().Audio
		sort.SliceStable(valid, func(i, j int) bool { return betterStream(valid[i], valid[j], preferred) })
		return valid, nil
	}
	if lastErr != nil {
		return nil, fmt.Errorf("não foi possível iniciar este episódio: %w", lastErr)
	}
	return nil, fmt.Errorf("nenhuma fonte de vídeo disponível para este episódio")
}
func (s *Service) Play(id string, a domain.Anime, episodes []domain.Episode, index int, resume bool) error {
	return s.play(id, a, episodes, index, resume, nil)
}

func (s *Service) play(id string, a domain.Anime, episodes []domain.Episode, index int, resume bool, previous *playback) error {
	if index < 0 || index >= len(episodes) {
		return fmt.Errorf("episódio inválido")
	}
	s.playMu.Lock()
	if previous != nil && !s.canAutoplay(*previous) {
		s.playMu.Unlock()
		return nil
	}
	s.playRequest++
	request := s.playRequest
	s.mu.Lock()
	old := s.current
	clearFinished := old.ID != "" && old.Finished
	if clearFinished {
		s.current = playback{}
	}
	s.mu.Unlock()
	ctx, end := s.operation("play", 45*time.Second)
	s.playMu.Unlock()
	defer end()
	if clearFinished {
		s.player.Stop()
		if old.Release != nil {
			old.Release()
		}
		s.discord.Update("", 0)
		s.emit("player", nil)
	}
	ep := episodes[index]
	streams, e := s.resolveCandidates(ctx, a, ep)
	if e != nil {
		return e
	}
	s.playMu.Lock()
	defer s.playMu.Unlock()
	if e = ctx.Err(); e != nil {
		return e
	}
	position := 0.0
	if resume {
		var h domain.History
		if s.db.Get("history", a.Key(), &h) == nil && !h.NeedsResolve && h.Episode.Key() == ep.Key() {
			position = h.Position
		}
	}
	settings := s.Settings()
	var session string
	var activeRelease func()
	var lastStartErr error
	started := false
	for i, stream := range streams {
		if e = ctx.Err(); e != nil {
			s.player.Stop()
			if activeRelease != nil {
				activeRelease()
			}
			return e
		}
		u, release := s.gateway.Register(stream)
		session = media.ID()
		s.mu.Lock()
		old = s.current
		s.current = playback{ID: session, Anime: a, Episodes: append([]domain.Episode{}, episodes...), Index: index, Release: release, Request: request, FallbackRemaining: len(streams) - i - 1, StartPosition: position, Source: stream.Source, Height: max(stream.Height, streamQualityHeight(stream)), Bandwidth: stream.Bandwidth}
		s.mu.Unlock()
		s.player.Stop()
		if activeRelease != nil {
			activeRelease()
		} else if old.Release != nil {
			old.Release()
		}
		activeRelease = release
		// The player process belongs to the service lifetime, not this Play
		// operation: end() cancels the operation context as soon as startup returns.
		if e = s.player.Start(s.ctx, u, settings.PlayerMode, settings.PlayerPath, position, session); e != nil {
			lastStartErr = e
			continue
		}
		started = true
		if settings.PlayerMode == "mpv" {
			go s.monitorStartup(request, session, streams[i+1:], position, settings)
		}
		break
	}
	if !started {
		if activeRelease != nil {
			activeRelease()
		}
		if session != "" {
			s.mu.Lock()
			if s.current.ID == session {
				s.current.Release = nil
			}
			s.mu.Unlock()
			s.onPlayer(player.State{Session: session, Error: fmt.Sprintf("não foi possível abrir o MPV em nenhuma fonte: %v", lastStartErr)})
		}
		if lastStartErr != nil {
			return lastStartErr
		}
		return fmt.Errorf("nenhuma fonte de vídeo disponível para este episódio")
	}
	a.Availability = nil
	s.db.Put("history", a.Key(), domain.History{Anime: a, Episode: ep, Position: position, Updated: time.Now().Unix()})
	if index+1 < len(episodes) {
		go func() {
			prefetch, cancel := context.WithTimeout(s.ctx, 15*time.Second)
			defer cancel()
			s.catalog.Resolve(prefetch, episodes[index+1], settings.Audio)
		}()
	}
	return nil
}

var playerStartupTimeout = 10 * time.Second

func (s *Service) monitorStartup(request uint64, session string, remaining []domain.Stream, startPosition float64, settings domain.Settings) {
	timer := time.NewTimer(playerStartupTimeout)
	defer timer.Stop()
	ticker := time.NewTicker(250 * time.Millisecond)
	defer ticker.Stop()
	for {
		if !s.isCurrentAttempt(request, session) {
			return
		}
		state := s.player.State()
		if state.Session != session {
			return
		}
		if state.Position > startPosition+0.75 {
			return
		}
		if state.Error != "" || !state.Playing {
			break
		}
		select {
		case <-s.ctx.Done():
			return
		case <-timer.C:
			goto retry
		case <-ticker.C:
		}
	}

retry:
	s.startNextCandidate(request, session, remaining, startPosition, settings)
}

func (s *Service) isCurrentAttempt(request uint64, session string) bool {
	s.playMu.Lock()
	defer s.playMu.Unlock()
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.playRequest == request && s.current.Request == request && s.current.ID == session
}

func (s *Service) startNextCandidate(request uint64, previousSession string, remaining []domain.Stream, startPosition float64, settings domain.Settings) {
	s.playMu.Lock()
	defer s.playMu.Unlock()
	s.mu.Lock()
	if s.playRequest != request || s.current.Request != request || s.current.ID != previousSession {
		s.mu.Unlock()
		return
	}
	previous := s.current
	s.mu.Unlock()
	for i, stream := range remaining {
		if s.ctx.Err() != nil || s.playRequest != request {
			return
		}
		u, release := s.gateway.Register(stream)
		session := media.ID()
		s.mu.Lock()
		if s.current.Request != request || s.current.ID != previousSession {
			s.mu.Unlock()
			release()
			return
		}
		s.current.ID = session
		s.current.Release = release
		s.current.Finished = false
		s.current.FallbackRemaining = len(remaining) - i - 1
		s.current.StartPosition = startPosition
		s.current.Source = stream.Source
		s.current.Height = max(stream.Height, streamQualityHeight(stream))
		s.current.Bandwidth = stream.Bandwidth
		s.mu.Unlock()
		s.player.Stop()
		if previous.Release != nil {
			// Stop the process before releasing the gateway session it was reading.
			previous.Release()
		}
		previousSession = session
		previous = playback{ID: session, Request: request, Release: release}
		if err := s.player.Start(s.ctx, u, settings.PlayerMode, settings.PlayerPath, startPosition, session); err != nil {
			release()
			s.mu.Lock()
			if s.current.ID == session {
				s.current.Release = nil
			}
			s.mu.Unlock()
			continue
		}
		if settings.PlayerMode == "mpv" {
			go s.monitorStartup(request, session, remaining[i+1:], startPosition, settings)
		}
		return
	}
	s.mu.Lock()
	current := s.current
	s.mu.Unlock()
	if current.Request == request && current.ID != "" {
		s.player.Stop()
		if current.Release != nil {
			current.Release()
		}
		s.mu.Lock()
		if s.current.ID == current.ID {
			s.current.Release = nil
		}
		s.mu.Unlock()
		s.onPlayer(player.State{Session: current.ID, Error: "Nenhuma fonte iniciou a reprodução no MPV"})
	}
}

// Called with playMu held. A pending manual selection also supersedes autoplay.
func (s *Service) canAutoplay(previous playback) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.current.ID == previous.ID && s.playRequest == previous.Request && s.settings.Autoplay && s.ctx.Err() == nil
}
func (s *Service) onPlayer(state player.State) {
	s.mu.Lock()
	p := s.current
	if p.ID != state.Session || len(p.Episodes) == 0 {
		s.mu.Unlock()
		return
	}
	ep := p.Episodes[p.Index]
	if p.FallbackRemaining > 0 && state.Position <= p.StartPosition+0.75 && (!state.Playing || state.Error != "") {
		// The startup monitor will try the next validated candidate. Keep the
		// transient MPV error out of the UI while that recovery is in progress.
		s.mu.Unlock()
		return
	}
	save := time.Since(p.Saved) > 5*time.Second || !state.Playing
	if save {
		s.current.Saved = time.Now()
	}
	finish := !state.Playing && !p.Finished
	if finish {
		s.current.Finished = true
	}
	autoplay := s.settings.Autoplay
	s.mu.Unlock()
	if state.Playing || state.Paused {
		s.discord.UpdatePlayback(integrations.DiscordPlayback{
			Title:        p.Anime.Title,
			Season:       ep.Season,
			Episode:      ep.Number,
			EpisodeTitle: ep.Title,
			Position:     state.Position,
			Playing:      state.Playing,
			Paused:       state.Paused,
		})
	} else {
		s.discord.Update("", 0)
	}
	s.emit("player", PlayerEvent{state, p.Anime, ep})
	if save {
		p.Anime.Availability = nil
		s.db.Put("history", p.Anime.Key(), domain.History{Anime: p.Anime, Episode: ep, Position: state.Position, Updated: time.Now().Unix()})
	}
	if finish {
		if p.Release != nil {
			p.Release()
		}
		if state.Watched && !p.Local {
			go s.syncWatched(p.Anime, ep)
		}
		if state.EOF && autoplay && !p.Local && p.Index+1 < len(p.Episodes) {
			go func() {
				if e := s.play("autoplay", p.Anime, p.Episodes, p.Index+1, false, &p); e != nil && e != context.Canceled {
					s.emit("error", e.Error())
				}
			}()
		}
	}
}
func (s *Service) syncWatched(a domain.Anime, ep domain.Episode) {
	// A season must have an explicit tracker mapping before a progress mutation.
	if ep.Season > 1 && a.Season != ep.Season {
		return
	}
	ctx, cancel := context.WithTimeout(s.ctx, 30*time.Second)
	defer cancel()
	for _, account := range s.accounts.Profiles() {
		if !account.Connected || (account.Provider != "anilist" && account.Provider != "mal") {
			continue
		}
		id := a.AniListID
		if account.Provider == "mal" {
			id = a.MALID
		}
		if id <= 0 {
			continue
		}
		if e := s.accounts.Sync(ctx, account.Provider, integrations.MALClientID, id, int(ep.Number), a.EpisodeCount); e != nil {
			s.emit("error", "Sincronização: "+e.Error())
		}
	}
}
func (s *Service) PlayerCommand(command string, value float64) error {
	if command == "stop" {
		s.playMu.Lock()
		s.playRequest++
		s.Cancel("play")
		s.mu.Lock()
		old := s.current
		s.current = playback{}
		s.mu.Unlock()
		s.player.Stop()
		if old.Release != nil {
			old.Release()
		}
		s.discord.Update("", 0)
		s.emit("player", nil)
		s.playMu.Unlock()
		return nil
	}
	return s.player.Command(command, value)
}
func (s *Service) Adjacent(delta int) error {
	s.mu.Lock()
	p := s.current
	s.mu.Unlock()
	if p.Local {
		return fmt.Errorf("selecione outro arquivo na biblioteca offline")
	}
	return s.Play("adjacent", p.Anime, p.Episodes, p.Index+delta, false)
}
func (s *Service) Enqueue(a domain.Anime, episodes []domain.Episode) ([]domain.Download, error) {
	out := []domain.Download{}
	for _, ep := range episodes {
		d, e := s.queue.Enqueue(a, ep, false)
		if e != nil {
			return out, e
		}
		out = append(out, d)
	}
	return out, nil
}
func (s *Service) Downloads() []domain.Download { return s.queue.List() }
func (s *Service) CancelDownload(id string)     { s.queue.Cancel(id); s.Cancel(id) }
func (s *Service) LocalFiles() ([]domain.LocalFile, error) {
	return downloads.Scan(s.Settings().DownloadsDir, s.db)
}
func (s *Service) DeleteFile(path string) error {
	return downloads.Delete(s.Settings().DownloadsDir, path, s.db)
}
func (s *Service) OpenDownloads() error { return platform.Open(s.Settings().DownloadsDir) }
func (s *Service) OpenLocalFolder(path string) error {
	root, err := filepath.EvalSymlinks(s.Settings().DownloadsDir)
	if err != nil {
		return err
	}
	resolved, err := filepath.EvalSymlinks(path)
	if err != nil {
		return err
	}
	if !platform.Within(root, resolved) {
		return fmt.Errorf("arquivo fora da biblioteca")
	}
	info, err := os.Stat(resolved)
	if err != nil {
		return err
	}
	if !info.Mode().IsRegular() {
		return fmt.Errorf("selecione um arquivo da biblioteca")
	}
	return platform.RevealFile(resolved)
}
func (s *Service) PlayLocal(path string) error {
	root := s.Settings().DownloadsDir
	resolved, e := filepath.EvalSymlinks(path)
	if e != nil {
		return e
	}
	resolvedRoot, e := filepath.EvalSymlinks(root)
	if e != nil || !platform.Within(resolvedRoot, resolved) {
		return fmt.Errorf("arquivo fora da biblioteca")
	}
	st, e := os.Stat(resolved)
	if e != nil {
		return e
	}
	if !st.Mode().IsRegular() {
		return fmt.Errorf("selecione um arquivo de vídeo")
	}
	file := domain.LocalFile{Path: resolved, Title: filepath.Base(resolved)}
	if files, err := s.LocalFiles(); err == nil {
		for _, f := range files {
			if f.Path == path || f.Path == resolved {
				file = f
				break
			}
		}
	}
	if file.Kind == "manga" {
		return fmt.Errorf("abra este arquivo no leitor de mangá")
	}
	s.playMu.Lock()
	defer s.playMu.Unlock()
	s.playRequest++
	s.Cancel("play")
	session := media.ID()
	a := domain.Anime{ID: resolved, Provider: "local", Title: file.Title, Cover: file.Cover}
	ep := domain.Episode{ID: resolved, Provider: "local", AnimeID: resolved, Title: filepath.Base(resolved), Number: file.Episode, URL: resolved}
	if download, ok := s.offlineDownload(resolved); ok {
		a = download.Anime
		ep = localEpisode(download, resolved)
	}
	s.mu.Lock()
	old := s.current
	s.current = playback{ID: session, Anime: a, Episodes: []domain.Episode{ep}, Request: s.playRequest, Local: true}
	s.mu.Unlock()
	s.player.Stop()
	if old.Release != nil {
		old.Release()
	}
	v := s.Settings()
	position := 0.0
	var history domain.History
	if s.db.Get("history", a.Key(), &history) == nil && !history.NeedsResolve && history.Episode.Season == ep.Season && history.Episode.Number == ep.Number {
		position = history.Position
	}
	e = s.player.Start(s.ctx, resolved, v.PlayerMode, v.PlayerPath, position, session)
	if e != nil {
		s.onPlayer(player.State{Session: session, Error: e.Error()})
	}
	return e
}

func (s *Service) offlineDownload(path string) (domain.Download, bool) {
	item, ok := s.completedDownload(path)
	if !ok {
		return domain.Download{}, false
	}
	if info, err := os.Stat(path); err != nil || !info.Mode().IsRegular() {
		return domain.Download{}, false
	}
	return item, true
}

func (s *Service) completedDownload(path string) (domain.Download, bool) {
	path = normalizedLocalPath(path)
	for _, item := range s.queue.List() {
		if item.Kind != "anime" || item.Status != "done" || item.Path == "" {
			continue
		}
		if normalizedLocalPath(item.Path) == path && item.Anime.Key() != ":" {
			return item, true
		}
	}
	return domain.Download{}, false
}

func localEpisode(download domain.Download, path string) domain.Episode {
	episode := download.Episode
	episode.ID = path
	episode.AnimeID = download.Anime.ID
	episode.Provider = "local"
	episode.URL = path
	return episode
}

func normalizedLocalPath(path string) string {
	absolute, err := filepath.Abs(path)
	if err == nil {
		path = absolute
	}
	path = filepath.Clean(path)
	if runtime.GOOS == "windows" {
		path = strings.ToLower(path)
	}
	return path
}
func (s *Service) MangaSearch(id, q string) ([]domain.Manga, error) {
	ctx, end := s.operation(id, 40*time.Second)
	defer end()
	return s.manga.Search(ctx, q)
}
func (s *Service) MangaDiscover(id string) (domain.MangaDiscovery, error) {
	ctx, end := s.operation(id, 30*time.Second)
	defer end()
	const cacheKey = "manga:discovery:v1"
	var cached domain.MangaDiscovery
	hasCached, stale := s.db.CacheGet(cacheKey, &cached)
	if hasCached && !stale {
		return cached, nil
	}
	fresh, err := s.manga.Discover(ctx)
	if err != nil {
		if hasCached {
			cached.Warning = "O catálogo está temporariamente indisponível; mostrando os dados salvos."
			return cached, nil
		}
		return domain.MangaDiscovery{}, err
	}
	if err := s.db.CachePut(cacheKey, fresh, 15*time.Minute, 6*time.Hour); err != nil {
		fresh.Warning = strings.TrimSpace(strings.Join([]string{fresh.Warning, "Não foi possível atualizar o cache local."}, "; "))
	}
	return fresh, nil
}
func (s *Service) MangaByCategory(id, categoryID string) ([]domain.Manga, error) {
	ctx, end := s.operation(id, 30*time.Second)
	defer end()
	key := "manga:category:v1:" + categoryID
	var cached []domain.Manga
	hasCached, stale := s.db.CacheGet(key, &cached)
	if hasCached && !stale {
		return cached, nil
	}
	fresh, err := s.manga.ByCategory(ctx, categoryID)
	if err != nil {
		if hasCached {
			return cached, nil
		}
		return nil, err
	}
	_ = s.db.CachePut(key, fresh, 15*time.Minute, 6*time.Hour)
	return fresh, nil
}
func (s *Service) Chapters(id, mangaID string) ([]domain.Chapter, error) {
	ctx, end := s.operation(id, 90*time.Second)
	defer end()
	return s.manga.Chapters(ctx, mangaID)
}
func (s *Service) ChaptersLanguage(id, mangaID, language string) ([]domain.Chapter, error) {
	ctx, end := s.operation(id, 90*time.Second)
	defer end()
	return s.manga.ChaptersLanguage(ctx, mangaID, language)
}
func (s *Service) Pages(id, chapterID string) ([]string, error) {
	ctx, end := s.operation(id, 30*time.Second)
	defer end()
	pages, e := s.manga.PageSources(ctx, chapterID)
	if e != nil {
		return nil, e
	}
	urls := []string{}
	releases := []func(){}
	for _, p := range pages {
		u, release := s.gateway.RegisterImage(p.URL, p.Alternatives)
		urls = append(urls, u)
		releases = append(releases, release)
	}
	s.mu.Lock()
	if s.bookRelease != nil {
		s.bookRelease()
	}
	s.bookRelease = func() {
		for _, release := range releases {
			release()
		}
	}
	s.mu.Unlock()
	return urls, nil
}
func (s *Service) MangaHistory() ([]domain.MangaProgress, error) {
	return store.DecodeList[domain.MangaProgress](s.db, "manga_history")
}
func (s *Service) SaveMangaProgress(p domain.MangaProgress) error {
	p.Updated = time.Now().Unix()
	return s.db.Put("manga_history", p.Manga.ID, p)
}
func (s *Service) DownloadManga(id string, m domain.Manga, chapters []domain.Chapter) error {
	for _, ch := range chapters {
		if _, e := s.queue.EnqueueManga(m, ch); e != nil {
			return e
		}
	}
	return nil
}
func (s *Service) Accounts() []integrations.Account { return s.accounts.Profiles() }
func (s *Service) Login(id, provider string) error {
	ctx, end := s.operation(id, 2*time.Minute)
	defer end()
	return s.accounts.Login(ctx, provider, integrations.MALClientID)
}
func (s *Service) Logout(provider string) error { return s.accounts.Logout(provider) }
func (s *Service) RefreshAccount(id, provider string) (integrations.Account, error) {
	ctx, end := s.operation(id, 30*time.Second)
	defer end()
	return s.accounts.Profile(ctx, provider, integrations.MALClientID)
}
func (s *Service) CheckUpdate(id string) (update.Info, error) {
	ctx, end := s.operation(id, 30*time.Second)
	defer end()
	return s.updater.Check(ctx)
}
func (s *Service) DownloadUpdate(id string, info update.Info) (string, error) {
	ctx, end := s.operation(id, 30*time.Minute)
	defer end()
	path, e := s.updater.Download(ctx, info, filepath.Join(s.db.Dir, "updates"), func(n int) { s.emit("update", map[string]any{"id": id, "percent": n}) })
	if e != nil {
		return "", e
	}
	sum, e := digestFile(path)
	if e != nil {
		return "", e
	}
	if e = s.db.Put("verified_updates", path, sum); e != nil {
		return "", e
	}
	return path, nil
}
func (s *Service) ClearCache() error { _, e := s.db.DB.Exec("DELETE FROM cache"); return e }

func (s *Service) Diagnose() Diagnosis {
	d := Diagnosis{Platform: runtime.GOOS + "/" + runtime.GOARCH, DataDir: s.db.Dir, Dependencies: map[string]string{}, Discord: s.discord.Connected()}
	for _, name := range []string{"mpv", "ffmpeg", "ffprobe"} {
		path, e := platform.Binary(name)
		if e != nil {
			path = e.Error()
		}
		d.Dependencies[name] = path
	}
	return d
}
func (s *Service) OfflinePages(path string) ([]string, error) {
	root, e := filepath.EvalSymlinks(s.Settings().DownloadsDir)
	if e != nil {
		return nil, e
	}
	p, e := filepath.EvalSymlinks(path)
	if e != nil {
		return nil, e
	}
	if !platform.Within(root, p) {
		return nil, fmt.Errorf("arquivo fora da biblioteca")
	}
	pages, release, e := s.gateway.Archive(p)
	if e != nil {
		return nil, e
	}
	s.mu.Lock()
	if s.bookRelease != nil {
		s.bookRelease()
	}
	s.bookRelease = release
	s.mu.Unlock()
	return pages, nil
}
