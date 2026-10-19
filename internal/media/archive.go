package media

import (
	"archive/zip"
	"fmt"
	"io"
	"net/http"
	"path/filepath"
	"sort"
	"strings"
)

// Archive exposes random capability URLs and opens the ZIP only during reads.
func (g *Gateway) Archive(path string) ([]string, func(), error) {
	z, e := zip.OpenReader(path)
	if e != nil {
		return nil, nil, e
	}
	defer z.Close()
	names := []string{}
	for _, f := range z.File {
		ext := strings.ToLower(filepath.Ext(f.Name))
		if !f.FileInfo().IsDir() && (ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".webp" || ext == ".avif") {
			if f.UncompressedSize64 > 32<<20 {
				return nil, nil, fmt.Errorf("página excessivamente grande")
			}
			names = append(names, f.Name)
		}
	}
	sort.Strings(names)
	session := ID()
	urls := []string{}
	g.mu.Lock()
	for _, name := range names {
		key := session + "/" + ID()
		g.archives[key] = archivePage{path, name}
		urls = append(urls, g.base+"/archive/"+key)
	}
	g.mu.Unlock()
	return urls, func() {
		g.mu.Lock()
		defer g.mu.Unlock()
		for k := range g.archives {
			if strings.HasPrefix(k, session+"/") {
				delete(g.archives, k)
			}
		}
	}, nil
}

type archivePage struct{ Path, Name string }

func (g *Gateway) serveArchive(w http.ResponseWriter, r *http.Request) {
	g.mu.Lock()
	page, ok := g.archives[strings.TrimPrefix(r.URL.Path, "/archive/")]
	g.mu.Unlock()
	if !ok {
		http.NotFound(w, r)
		return
	}
	z, e := zip.OpenReader(page.Path)
	if e != nil {
		http.NotFound(w, r)
		return
	}
	defer z.Close()
	for _, f := range z.File {
		if f.Name != page.Name {
			continue
		}
		reader, e := f.Open()
		if e != nil {
			http.Error(w, "página indisponível", 500)
			return
		}
		defer reader.Close()
		w.Header().Set("Cache-Control", "private, max-age=3600")
		w.Header().Set("Content-Type", map[string]string{".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".avif": "image/avif"}[strings.ToLower(filepath.Ext(f.Name))])
		io.Copy(w, io.LimitReader(reader, 32<<20))
		return
	}
	http.NotFound(w, r)
}
