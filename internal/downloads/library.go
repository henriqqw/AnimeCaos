package downloads

import (
	"encoding/json"
	"fmt"
	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/platform"
	"github.com/henriqqw/animecaos/internal/store"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

var episodeRE = regexp.MustCompile(`(?i)^(.*?)\s*-\s*(?:EP(\d+)|S\d+E(\d+(?:\.\d+)?))`)

func Scan(dir string, s *store.Store) ([]domain.LocalFile, error) {
	out := []domain.LocalFile{}
	known, _ := store.DecodeList[domain.LocalFile](s, "local")
	byPath := map[string]domain.LocalFile{}
	for _, x := range known {
		byPath[x.Path] = x
	}
	e := filepath.WalkDir(dir, func(path string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.IsDir() {
			return nil
		}
		if d.Type()&os.ModeSymlink != 0 {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(path))
		kind := "anime"
		if ext == ".cbz" {
			kind = "manga"
		} else if !strings.Contains("|.mp4|.mkv|.webm|.m4v|.avi|.ts|.mov|", "|"+ext+"|") {
			return nil
		}
		if strings.Contains(d.Name(), ".part") || strings.HasPrefix(d.Name(), ".") {
			return nil
		}
		st, e := d.Info()
		if e != nil {
			return e
		}
		v, ok := byPath[path]
		if !ok {
			v = domain.LocalFile{Path: path, Title: strings.TrimSuffix(d.Name(), ext), Kind: kind}
			if m := episodeRE.FindStringSubmatch(d.Name()); len(m) > 0 {
				v.Title = strings.TrimSpace(m[1])
				v.Episode, _ = strconv.ParseFloat(m[2]+m[3], 64)
				var meta struct {
					Anime string `json:"anime"`
					Cover string `json:"cover_path"`
				}
				if b, e := os.ReadFile(filepath.Join(filepath.Dir(path), v.Title+".meta.json")); e == nil {
					if json.Unmarshal(b, &meta) == nil && meta.Anime != "" {
						v.Title = meta.Anime
						v.Cover = meta.Cover
					}
				}
			}
			if kind == "manga" {
				v.Title = filepath.Base(filepath.Dir(path)) + " / " + v.Title
			}
		}
		v.Size = st.Size()
		out = append(out, v)
		return nil
	})
	if os.IsNotExist(e) {
		e = nil
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Title == out[j].Title {
			return out[i].Episode < out[j].Episode
		}
		return out[i].Title < out[j].Title
	})
	return out, e
}
func Delete(dir, path string, s *store.Store) error {
	realRoot, e := filepath.EvalSymlinks(dir)
	if e != nil {
		return e
	}
	real, e := filepath.EvalSymlinks(path)
	if e != nil {
		return e
	}
	if !platform.Within(realRoot, real) {
		return fmt.Errorf("arquivo fora da biblioteca")
	}
	st, e := os.Stat(real)
	if e != nil {
		return e
	}
	if st.IsDir() {
		return fmt.Errorf("selecione um arquivo")
	}
	if e = os.Remove(real); e != nil {
		return e
	}
	return s.Delete("local", path)
}
