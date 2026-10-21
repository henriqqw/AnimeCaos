package downloads

import (
	"bufio"
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/media"
	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/platform"
	"github.com/henriqqw/animecaos/internal/store"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
)

type Resolver func(context.Context, domain.Anime, domain.Episode) (domain.Stream, error)
type MangaDownloader func(context.Context, domain.Manga, domain.Chapter, string, func(int, int)) (string, error)
type Queue struct {
	mu      sync.Mutex
	items   []domain.Download
	active  map[string]context.CancelFunc
	limit   int
	dir     string
	ctx     context.Context
	cancel  context.CancelFunc
	store   *store.Store
	gateway *media.Gateway
	resolve Resolver
	manga   MangaDownloader
	emit    func(domain.Download)
	stream  func(context.Context, string, map[string]string) (*http.Response, error)
	wg      sync.WaitGroup
}

func New(s *store.Store, g *media.Gateway, r Resolver, dir string, n int, emit func(domain.Download)) *Queue {
	ctx, cancel := context.WithCancel(context.Background())
	q := &Queue{active: map[string]context.CancelFunc{}, limit: n, dir: dir, ctx: ctx, cancel: cancel, store: s, gateway: g, resolve: r, emit: emit}
	client := netx.New()
	q.stream = client.Stream
	q.items, _ = store.DecodeList[domain.Download](s, "downloads")
	for i := range q.items {
		if pending(q.items[i].Status) {
			q.items[i].Status = "interrupted"
			s.Put("downloads", q.items[i].ID, q.items[i])
		}
	}
	return q
}
func (q *Queue) SetStreamClient(stream func(context.Context, string, map[string]string) (*http.Response, error)) {
	if stream != nil {
		q.stream = stream
	}
}
func pending(s string) bool { return s == "queued" || s == "resolving" || s == "downloading" }
func (q *Queue) List() []domain.Download {
	q.mu.Lock()
	defer q.mu.Unlock()
	return append([]domain.Download{}, q.items...)
}
func (q *Queue) Configure(dir string, n int) {
	q.mu.Lock()
	q.dir = dir
	q.limit = max(1, min(5, n))
	q.mu.Unlock()
	q.schedule()
}
func (q *Queue) Enqueue(a domain.Anime, ep domain.Episode, force bool) (domain.Download, error) {
	q.mu.Lock()
	for _, item := range q.items {
		if item.Kind == "anime" && item.Episode.Key() == ep.Key() && pending(item.Status) {
			q.mu.Unlock()
			return item, nil
		}
		if !force && item.Kind == "anime" && item.Episode.Key() == ep.Key() && item.Status == "done" {
			if st, e := os.Stat(item.Path); e == nil && st.Size() > 0 {
				q.mu.Unlock()
				return item, nil
			}
		}
	}
	item := domain.Download{ID: media.ID(), Anime: a, Episode: ep, Status: "queued", Kind: "anime"}
	q.items = append(q.items, item)
	q.mu.Unlock()
	q.changed(item)
	q.schedule()
	return item, nil
}
func (q *Queue) SetMangaDownloader(download MangaDownloader) {
	q.mu.Lock()
	q.manga = download
	q.mu.Unlock()
}

func (q *Queue) EnqueueManga(m domain.Manga, ch domain.Chapter) (domain.Download, error) {
	q.mu.Lock()
	if q.manga == nil {
		q.mu.Unlock()
		return domain.Download{}, fmt.Errorf("serviço de mangás indisponível")
	}
	for _, item := range q.items {
		if item.Kind != "manga" || item.Chapter == nil || item.Chapter.ID != ch.ID {
			continue
		}
		if pending(item.Status) {
			q.mu.Unlock()
			return item, nil
		}
		if item.Status == "done" {
			if st, err := os.Stat(item.Path); err == nil && st.Size() > 0 {
				q.mu.Unlock()
				return item, nil
			}
		}
	}
	item := domain.Download{ID: media.ID(), Kind: "manga", Manga: &m, Chapter: &ch, Anime: domain.Anime{Title: m.Title, Cover: m.Cover}, Episode: domain.Episode{ID: ch.ID, Provider: "mangadex", Title: "Cap. " + ch.Number + " · " + ch.Title}, Status: "queued"}
	q.items = append(q.items, item)
	q.mu.Unlock()
	q.changed(item)
	q.schedule()
	return item, nil
}
func (q *Queue) Cancel(id string) {
	q.mu.Lock()
	var item domain.Download
	for i := range q.items {
		if q.items[i].ID == id && pending(q.items[i].Status) {
			q.items[i].Status = "cancelled"
			item = q.items[i]
			if cancel := q.active[id]; cancel != nil {
				cancel()
			}
			break
		}
	}
	q.mu.Unlock()
	if item.ID != "" {
		q.changed(item)
	}
	q.schedule()
}
func (q *Queue) Close() { q.mu.Lock(); q.cancel(); q.mu.Unlock(); q.wg.Wait() }
func (q *Queue) changed(item domain.Download) {
	q.mu.Lock()
	for _, v := range q.items {
		if v.ID == item.ID {
			item = v
			break
		}
	}
	q.store.Put("downloads", item.ID, item)
	q.mu.Unlock()
	q.emit(item)
}
func (q *Queue) update(id string, fn func(*domain.Download)) {
	q.mu.Lock()
	var out domain.Download
	for i := range q.items {
		if q.items[i].ID == id && q.items[i].Status != "cancelled" {
			fn(&q.items[i])
			out = q.items[i]
			break
		}
	}
	q.mu.Unlock()
	if out.ID != "" {
		q.changed(out)
	}
}
func (q *Queue) schedule() {
	q.mu.Lock()
	defer q.mu.Unlock()
	if q.ctx.Err() != nil {
		return
	}
	for len(q.active) < q.limit {
		idx := -1
		for i := range q.items {
			if q.items[i].Status == "queued" {
				idx = i
				break
			}
		}
		if idx < 0 {
			return
		}
		item := q.items[idx]
		q.items[idx].Status = "resolving"
		ctx, cancel := context.WithCancel(q.ctx)
		q.active[item.ID] = cancel
		dir := q.dir
		q.wg.Add(1)
		go func() {
			defer q.wg.Done()
			defer cancel()
			q.update(item.ID, func(x *domain.Download) { x.Status = "resolving" })
			e := q.run(ctx, item, dir)
			if e != nil {
				q.update(item.ID, func(x *domain.Download) {
					if ctx.Err() != nil {
						x.Status = "cancelled"
					} else {
						x.Status = "failed"
					}
					x.Error = e.Error()
				})
			}
			q.mu.Lock()
			delete(q.active, item.ID)
			q.mu.Unlock()
			q.schedule()
		}()
	}
}
func (q *Queue) run(ctx context.Context, item domain.Download, dir string) error {
	if item.Kind == "manga" {
		q.mu.Lock()
		download := q.manga
		q.mu.Unlock()
		if download == nil || item.Manga == nil || item.Chapter == nil {
			return fmt.Errorf("metadados do capítulo indisponíveis")
		}
		q.update(item.ID, func(x *domain.Download) { x.Status = "downloading" })
		started := time.Now()
		path, err := download(ctx, *item.Manga, *item.Chapter, dir, func(n, total int) {
			q.update(item.ID, func(x *domain.Download) {
				if total > 0 {
					x.Percent = float64(n) * 100 / float64(total)
				}
				x.Speed = fmt.Sprintf("%d/%d páginas", n, total)
				if n > 0 {
					x.ETA = fmt.Sprintf("%.0fs", time.Since(started).Seconds()*float64(total-n)/float64(n))
				}
			})
		})
		if err != nil {
			return err
		}
		st, err := os.Stat(path)
		if err != nil {
			return err
		}
		if err = q.store.Put("local", path, domain.LocalFile{Path: path, Title: item.Manga.Title + " / " + item.Episode.Title, Cover: item.Manga.Cover, Kind: "manga", Size: st.Size()}); err != nil {
			return err
		}
		q.update(item.ID, func(x *domain.Download) { x.Status = "done"; x.Percent = 100; x.Path = path })
		return nil
	}
	s, e := q.resolve(ctx, item.Anime, item.Episode)
	if e != nil {
		return e
	}
	if e = media.Validate(ctx, s); e != nil {
		return e
	}
	s, e = media.Best(ctx, s)
	if e != nil {
		return e
	}
	u, release := q.gateway.Register(s)
	defer release()
	folder := filepath.Join(dir, platform.SafeName(item.Anime.Title))
	if e = os.MkdirAll(folder, 0755); e != nil {
		return e
	}
	ext := ".mp4"
	if s.Kind == "hls" {
		ext = ".mkv"
	}
	name := fmt.Sprintf("%s - S%02dE%s-%s%s", platform.SafeName(item.Anime.Title), item.Episode.Season, strconv.FormatFloat(item.Episode.Number, 'f', -1, 64), platform.SafeName(s.Audio), ext)
	if item.Episode.Season <= 0 || item.Episode.Number <= 0 {
		seasonTag, episodeTag := "??", "??"
		if item.Episode.Season > 0 {
			seasonTag = fmt.Sprintf("%02d", item.Episode.Season)
		}
		if item.Episode.Number > 0 {
			episodeTag = strconv.FormatFloat(item.Episode.Number, 'f', -1, 64)
		}
		identity := sha256.Sum256([]byte(item.Episode.Key()))
		name = fmt.Sprintf("%s - S%sE%s-%x-%s%s", platform.SafeName(item.Anime.Title), seasonTag, episodeTag, identity[:4], platform.SafeName(s.Audio), ext)
	}
	dest := filepath.Join(folder, name)
	if existing, statErr := os.Stat(dest); statErr == nil {
		if existing.Size() > 0 {
			q.update(item.ID, func(x *domain.Download) { x.Status = "done"; x.Percent = 100; x.Path = dest })
			return nil
		}
		if err := os.Remove(dest); err != nil {
			return fmt.Errorf("não foi possível substituir um arquivo vazio existente: %w", err)
		}
	}
	tmp := filepath.Join(folder, "."+item.ID+".part"+ext)
	defer os.Remove(tmp)
	q.update(item.ID, func(x *domain.Download) { x.Status = "downloading" })
	if s.Kind == "hls" {
		e = q.hls(ctx, item.ID, u, tmp)
	} else {
		e = q.direct(ctx, item.ID, u, tmp)
	}
	if e != nil {
		return e
	}
	if ctx.Err() != nil {
		return ctx.Err()
	}
	st, e := os.Stat(tmp)
	if e != nil || st.Size() == 0 {
		return fmt.Errorf("download sem conteúdo")
	}
	if e = platform.Publish(tmp, dest); e != nil {
		return e
	}
	meta := domain.LocalFile{Path: dest, Title: item.Anime.Title, Episode: item.Episode.Number, Size: st.Size(), Cover: item.Anime.Cover, Kind: "anime"}
	q.store.Put("local", dest, meta)
	if b, err := json.Marshal(map[string]string{"anime": meta.Title, "cover_path": meta.Cover}); err == nil {
		os.WriteFile(filepath.Join(folder, platform.SafeName(meta.Title)+".meta.json"), b, 0600)
	}
	q.update(item.ID, func(x *domain.Download) { x.Status = "done"; x.Percent = 100; x.Path = dest })
	return nil
}
func (q *Queue) direct(ctx context.Context, id, u, path string) error {
	r, e := q.stream(ctx, u, nil)
	if e != nil {
		return e
	}
	defer r.Body.Close()
	if r.StatusCode != 200 {
		return fmt.Errorf("download HTTP %d", r.StatusCode)
	}
	f, e := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if e != nil {
		return e
	}
	defer f.Close()
	var total int64
	start := time.Now()
	last := start
	buf := make([]byte, 128<<10)
	for {
		n, err := r.Body.Read(buf)
		if n > 0 {
			written, e := f.Write(buf[:n])
			if e != nil {
				return e
			}
			if written != n {
				return io.ErrShortWrite
			}
			total += int64(n)
			if time.Since(last) > 300*time.Millisecond {
				last = time.Now()
				q.update(id, func(x *domain.Download) {
					if r.ContentLength > 0 {
						x.Percent = float64(total) * 100 / float64(r.ContentLength)
					}
					speed := float64(total) / time.Since(start).Seconds()
					x.Speed = fmt.Sprintf("%.1f MB/s", speed/(1<<20))
					if speed > 0 && r.ContentLength > 0 {
						x.ETA = fmt.Sprintf("%.0fs", float64(r.ContentLength-total)/speed)
					}
				})
			}
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
	}
	if r.ContentLength >= 0 && total != r.ContentLength {
		return io.ErrUnexpectedEOF
	}
	return f.Sync()
}
func (q *Queue) hls(ctx context.Context, id, u, path string) error {
	bin, e := platform.Binary("ffmpeg")
	if e != nil {
		return e
	}
	duration := 0.0
	if probe, err := platform.Binary("ffprobe"); err == nil {
		pc, done := context.WithTimeout(ctx, 20*time.Second)
		command := exec.CommandContext(pc, probe, "-v", "error", "-allowed_extensions", "ALL", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", u)
		platform.HideConsole(command)
		if b, err := command.Output(); err == nil {
			duration, _ = strconv.ParseFloat(strings.TrimSpace(string(b)), 64)
		}
		done()
	}
	cmd := exec.CommandContext(ctx, bin, "-nostdin", "-hide_banner", "-loglevel", "error", "-xerror", "-allowed_extensions", "ALL", "-i", u, "-map", "0:v:0?", "-map", "0:a:0?", "-c", "copy", "-progress", "pipe:1", "-n", path)
	platform.HideConsole(cmd)
	out, e := cmd.StdoutPipe()
	if e != nil {
		return e
	}
	var errout strings.Builder
	cmd.Stderr = &errout
	if e = cmd.Start(); e != nil {
		return e
	}
	scanner := bufio.NewScanner(out)
	started := time.Now()
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "out_time_us=") && duration > 0 {
			micros, _ := strconv.ParseFloat(strings.TrimPrefix(line, "out_time_us="), 64)
			seconds := micros / 1e6
			q.update(id, func(x *domain.Download) {
				x.Percent = min(99.9, seconds*100/duration)
				if seconds > 0 {
					x.ETA = fmt.Sprintf("%.0fs", max(0, duration-seconds)*time.Since(started).Seconds()/seconds)
				}
			})
		}
		if strings.HasPrefix(line, "speed=") {
			v := strings.TrimPrefix(line, "speed=")
			q.update(id, func(x *domain.Download) { x.Speed = v })
		}
	}
	if e = cmd.Wait(); e != nil {
		return fmt.Errorf("FFmpeg: %s (%w)", strings.TrimSpace(errout.String()), e)
	}
	return scanner.Err()
}
