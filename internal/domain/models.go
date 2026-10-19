package domain

import "context"

type Anime struct {
	ID            string                `json:"id"`
	Provider      string                `json:"provider"`
	Title         string                `json:"title"`
	Titles        []string              `json:"titles"`
	PrimaryTitles []string              `json:"-"`
	Variants      []Anime               `json:"variants,omitempty"`
	URL           string                `json:"url"`
	Cover         string                `json:"cover"`
	Banner        string                `json:"banner"`
	Description   string                `json:"description"`
	Audio         string                `json:"audio"`
	Status        string                `json:"status"`
	Score         float64               `json:"score"`
	Year          int                   `json:"year"`
	Format        string                `json:"format"`
	MatchScore    float64               `json:"-"`
	SearchGroupID int                   `json:"-"`
	EpisodeCount  int                   `json:"episodeCount"`
	AniListID     int                   `json:"anilistId"`
	MALID         int                   `json:"malId"`
	Season        int                   `json:"season"`
	Availability  *PlaybackAvailability `json:"availability,omitempty"`
}

// PlaybackAvailability is a short-lived summary of a successful first-episode
// preflight. It intentionally contains no stream URLs or request headers.
type PlaybackAvailability struct {
	MaxHeight       int      `json:"maxHeight"`
	Quality         string   `json:"quality"`
	SourcesVerified []string `json:"sourcesVerified"`
	SampleEpisode   string   `json:"sampleEpisode"`
}

func (a Anime) Key() string { return a.Provider + ":" + a.ID }

type Episode struct {
	ID       string  `json:"id"`
	AnimeID  string  `json:"animeId"`
	Provider string  `json:"provider"`
	Title    string  `json:"title"`
	Number   float64 `json:"number"`
	Season   int     `json:"season"`
	URL      string  `json:"url"`
	Audio    string  `json:"audio"`
}

func (e Episode) Key() string { return e.Provider + ":" + e.ID }

type Stream struct {
	URL       string            `json:"url"`
	Kind      string            `json:"kind"`
	Audio     string            `json:"audio"`
	Qualities []string          `json:"qualities"`
	Source    string            `json:"source,omitempty"`
	Height    int               `json:"height,omitempty"`
	Bandwidth int               `json:"bandwidth,omitempty"`
	Headers   map[string]string `json:"headers"`
	Offline   bool              `json:"offline"`
}
type SearchResult struct {
	Items    []Anime  `json:"items"`
	Page     int      `json:"page"`
	HasNext  bool     `json:"hasNext"`
	Warnings []string `json:"warnings"`
}
type Detail struct {
	Anime    Anime     `json:"anime"`
	Episodes []Episode `json:"episodes"`
}
type AnimeProvider interface {
	Name() string
	Search(context.Context, string, int) (SearchResult, error)
	Details(context.Context, Anime) (Detail, error)
	Resolve(context.Context, Episode) ([]Stream, error)
}
type History struct {
	Anime        Anime   `json:"anime"`
	Episode      Episode `json:"episode"`
	Position     float64 `json:"position"`
	Updated      int64   `json:"updated"`
	LegacyIndex  int     `json:"legacyIndex"`
	NeedsResolve bool    `json:"needsResolve"`
}
type Settings struct {
	UIScale      float64 `json:"uiScale"`
	Theme        string  `json:"theme"`
	PlayerMode   string  `json:"playerMode"`
	PlayerPath   string  `json:"playerPath"`
	DownloadsDir string  `json:"downloadsDir"`
	Concurrent   int     `json:"concurrent"`
	AutoClose    bool    `json:"autoClose"`
	AutoCloseMS  int     `json:"autoCloseMs"`
	Autoplay     bool    `json:"autoplay"`
	Audio        string  `json:"audio"`
	Discord      bool    `json:"discord"`
	MALClientID  string  `json:"malClientId"`
	Width        int     `json:"width"`
	Height       int     `json:"height"`
	X            int     `json:"x"`
	Y            int     `json:"y"`
}
type Manga struct {
	ID          string   `json:"id"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	Cover       string   `json:"cover"`
	Status      string   `json:"status"`
	Languages   []string `json:"languages"`
}
type Chapter struct {
	ID       string `json:"id"`
	Title    string `json:"title"`
	Number   string `json:"number"`
	Volume   string `json:"volume"`
	Language string `json:"language"`
	Pages    int    `json:"pages"`
	Group    string `json:"group,omitempty"`
}
type MangaProgress struct {
	Manga   Manga   `json:"manga"`
	Chapter Chapter `json:"chapter"`
	Page    int     `json:"page"`
	Updated int64   `json:"updated"`
}
type Download struct {
	Manga   *Manga   `json:"manga,omitempty"`
	Chapter *Chapter `json:"chapter,omitempty"`
	ID      string   `json:"id"`
	Anime   Anime    `json:"anime"`
	Episode Episode  `json:"episode"`
	Status  string   `json:"status"`
	Percent float64  `json:"percent"`
	Speed   string   `json:"speed"`
	ETA     string   `json:"eta"`
	Error   string   `json:"error"`
	Path    string   `json:"path"`
	Kind    string   `json:"kind"`
}
type LocalFile struct {
	Path    string  `json:"path"`
	Title   string  `json:"title"`
	Episode float64 `json:"episode"`
	Size    int64   `json:"size"`
	Cover   string  `json:"cover"`
	Kind    string  `json:"kind"`
}
