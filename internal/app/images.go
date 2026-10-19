package app

import (
	"context"
	"crypto/md5"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"github.com/henriqqw/animecaos/internal/platform"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Image keeps covers available across restarts and offline sessions. Tokens and
// account credentials are never attached to image requests.
func (s *Service) Image(source string) (value string, resultErr error) {
	if source == "" {
		return "", nil
	}
	u, e := url.Parse(source)
	if e != nil {
		return "", e
	}
	var b []byte
	if u.Scheme == "http" || u.Scheme == "https" {
		sum := sha256.Sum256([]byte(source))
		dir := filepath.Join(s.db.Dir, "images")
		file := filepath.Join(dir, hex.EncodeToString(sum[:]))
		b, e = readCachedImage(file)
		if e != nil {
			// The legacy cache used MD5 URL names; keep those covers usable offline.
			legacyHash := md5.Sum([]byte(source))
			matches, _ := filepath.Glob(filepath.Join(s.db.Dir, "cache", "covers", hex.EncodeToString(legacyHash[:])+".*"))
			for _, candidate := range matches {
				if b, e = readCachedImage(candidate); e == nil {
					break
				}
			}
		}
		if e != nil {
			failureKey := "image-failed:" + hex.EncodeToString(sum[:])
			var failed bool
			if ok, _ := s.db.CacheGet(failureKey, &failed); ok && failed {
				return "", fmt.Errorf("imagem temporariamente indisponível")
			}
			defer func() {
				if resultErr != nil && s.ctx.Err() == nil {
					s.db.CachePut(failureKey, true, time.Hour, time.Hour)
				}
			}()
			ctx, cancel := context.WithTimeout(s.ctx, 15*time.Second)
			defer cancel()
			select {
			case s.imageSlots <- struct{}{}:
				defer func() { <-s.imageSlots }()
			case <-ctx.Done():
				return "", ctx.Err()
			}
			if cached, err := readCachedImage(file); err == nil {
				return "data:" + http.DetectContentType(cached) + ";base64," + base64.StdEncoding.EncodeToString(cached), nil
			}
			req, e := http.NewRequestWithContext(ctx, "GET", source, nil)
			if e != nil {
				return "", e
			}
			r, e := http.DefaultClient.Do(req)
			if e != nil {
				return "", e
			}
			defer r.Body.Close()
			if r.StatusCode != 200 {
				return "", fmt.Errorf("imagem HTTP %d", r.StatusCode)
			}
			b, e = io.ReadAll(io.LimitReader(r.Body, (10<<20)+1))
			if e != nil {
				return "", e
			}
			if len(b) > 10<<20 {
				return "", fmt.Errorf("imagem muito grande")
			}
			if !strings.HasPrefix(http.DetectContentType(b), "image/") {
				return "", fmt.Errorf("formato de imagem não reconhecido")
			}
			if e = os.MkdirAll(dir, 0700); e != nil {
				return "", e
			}
			tmp, e := os.CreateTemp(dir, "image-*.part")
			if e == nil {
				_, writeErr := tmp.Write(b)
				if writeErr == nil {
					writeErr = tmp.Sync()
				}
				closeErr := tmp.Close()
				if writeErr == nil && closeErr == nil {
					// Only replace a corrupt cache entry, never a valid concurrent write.
					if _, err := readCachedImage(file); err != nil {
						os.Remove(file)
					}
					platform.Publish(tmp.Name(), file)
				}
				os.Remove(tmp.Name())
			}
		}
	} else {
		path, e := filepath.EvalSymlinks(source)
		if e != nil {
			return "", e
		}
		allowed := false
		for _, root := range []string{s.db.Dir, s.Settings().DownloadsDir} {
			real, e := filepath.EvalSymlinks(root)
			if e == nil && platform.Within(real, path) {
				allowed = true
			}
		}
		if !allowed {
			return "", fmt.Errorf("imagem fora dos diretórios de dados")
		}
		f, e := os.Open(path)
		if e != nil {
			return "", e
		}
		defer f.Close()
		b, e = io.ReadAll(io.LimitReader(f, (10<<20)+1))
		if e != nil {
			return "", e
		}
		if len(b) > 10<<20 {
			return "", fmt.Errorf("imagem muito grande")
		}
	}
	kind := http.DetectContentType(b)
	if !strings.HasPrefix(kind, "image/") {
		return "", fmt.Errorf("imagem inválida")
	}
	return "data:" + kind + ";base64," + base64.StdEncoding.EncodeToString(b), nil
}

func readCachedImage(path string) ([]byte, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	b, err := io.ReadAll(io.LimitReader(f, (10<<20)+1))
	if err != nil {
		return nil, err
	}
	if len(b) > 10<<20 || !strings.HasPrefix(http.DetectContentType(b), "image/") {
		return nil, fmt.Errorf("cache de imagem inválido")
	}
	return b, nil
}
