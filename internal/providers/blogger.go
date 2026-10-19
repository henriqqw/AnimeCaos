package providers

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/url"
	"sort"
	"strconv"
	"strings"

	"github.com/henriqqw/animecaos/internal/domain"
)

// Blogger's public embedded player obtains its signed media URLs through this
// RPC. URLs expire; resolve them for each playback instead of persisting them.
func (p *OnlineCC) resolveBlogger(ctx context.Context, embed string) ([]domain.Stream, error) {
	u, err := url.Parse(embed)
	if err != nil || u.Query().Get("token") == "" {
		return nil, fmt.Errorf("player Blogger sem identificador de vídeo")
	}
	request, _ := json.Marshal([]any{u.Query().Get("token"), nil, false})
	batch, _ := json.Marshal([]any{[]any{[]any{"WcwnYd", string(request), nil, "generic"}}})
	endpoint := u.Scheme + "://" + u.Host + "/_/BloggerVideoPlayerUi/data/batchexecute?rpcids=WcwnYd"
	r, err := p.Client.Do(ctx, "POST", endpoint, []byte(url.Values{"f.req": {string(batch)}}.Encode()), map[string]string{
		"Content-Type": "application/x-www-form-urlencoded", "Referer": embed,
	})
	if err != nil {
		return nil, err
	}
	defer r.Body.Close()
	b, err := io.ReadAll(io.LimitReader(r.Body, 8<<20))
	if err != nil {
		return nil, err
	}
	return parseBlogger(b, embed)
}

func parseBlogger(b []byte, referer string) ([]domain.Stream, error) {
	// batchexecute may prefix JSON with XSSI protection and numeric chunk lengths.
	sawRPC := false
	lastStatus := -1
	formatCount := 0
	payloadType := "ausente"
	payloadFields := -1
	statusType := "ausente"
	for _, line := range strings.Split(string(b), "\n") {
		line = strings.TrimSpace(line)
		if !strings.HasPrefix(line, "[[") {
			continue
		}
		var rows [][]json.RawMessage
		if json.Unmarshal([]byte(line), &rows) != nil {
			continue
		}
		for _, row := range rows {
			if len(row) < 3 {
				continue
			}
			var rpc, payload string
			json.Unmarshal(row[1], &rpc)
			if rpc != "WcwnYd" {
				continue
			}
			sawRPC = true
			payloadType = bloggerJSONType(row[2])
			if json.Unmarshal(row[2], &payload) != nil {
				continue
			}
			var fields []json.RawMessage
			if json.Unmarshal([]byte(payload), &fields) != nil {
				continue
			}
			payloadFields = len(fields)
			if len(fields) == 0 {
				continue
			}
			statusType = bloggerJSONType(fields[0])
			if len(fields) < 3 {
				continue
			}
			var status int
			json.Unmarshal(fields[0], &status)
			lastStatus = status
			if status == 2 {
				return nil, fmt.Errorf("vídeo indisponível no Blogger")
			}
			type rendition struct {
				url    string
				height int
			}
			var formats [][]json.RawMessage
			json.Unmarshal(fields[2], &formats)
			formatCount += len(formats)
			var candidates []rendition
			for _, f := range formats {
				if len(f) < 2 {
					continue
				}
				var source string
				var format []int
				if json.Unmarshal(f[0], &source) != nil || json.Unmarshal(f[1], &format) != nil || len(format) == 0 {
					continue
				}
				if v, e := url.Parse(source); e != nil || (v.Scheme != "https" && v.Scheme != "http") {
					continue
				}
				candidates = append(candidates, rendition{source, map[int]int{7: 240, 18: 360, 22: 720, 37: 1080}[format[0]]})
			}
			sort.SliceStable(candidates, func(i, j int) bool { return candidates[i].height > candidates[j].height })
			out := []domain.Stream{}
			for _, f := range candidates {
				qualities := []string{}
				if f.height > 0 {
					qualities = append(qualities, strconv.Itoa(f.height)+"p")
				}
				out = append(out, domain.Stream{URL: f.url, Kind: "file", Qualities: qualities, Headers: map[string]string{"Referer": referer}})
			}
			if len(out) > 0 {
				return out, nil
			}
		}
	}
	if sawRPC && formatCount == 0 {
		if lastStatus == -1 {
			return nil, fmt.Errorf("RPC Blogger não retornou payload reconhecido (payload=%s, campos=%d, tipo_status=%s)", payloadType, payloadFields, statusType)
		}
		return nil, fmt.Errorf("RPC Blogger não publicou renditions (status=%d, formatos=0)", lastStatus)
	}
	if sawRPC {
		return nil, fmt.Errorf("RPC Blogger publicou %d formato(s), mas nenhum continha uma URL HTTP válida", formatCount)
	}
	return nil, fmt.Errorf("formato do player Blogger não reconhecido ou vídeo sem streams")
}

func bloggerJSONType(raw json.RawMessage) string {
	trimmed := strings.TrimSpace(string(raw))
	if trimmed == "" {
		return "vazio"
	}
	switch trimmed[0] {
	case '"':
		return "string"
	case '[':
		return "array"
	case '{':
		return "objeto"
	case 'n':
		return "null"
	case 't', 'f':
		return "booleano"
	default:
		return "número"
	}
}
