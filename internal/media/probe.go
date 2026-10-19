package media

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
)

type Info struct {
	VideoCodec string
	AudioCodec string
	Width      int
	Height     int
	Bitrate    int
	Duration   float64
}

// Probe reads video height/bitrate from a direct stream when ffprobe is
// installed. The caller should first validate the URL and use this only when
// provider or HLS metadata did not identify quality.
func Probe(ctx context.Context, stream domain.Stream) (int, int, error) {
	info, err := Inspect(ctx, stream)
	if err != nil {
		return 0, 0, err
	}
	if info.Height == 0 && info.Bitrate == 0 {
		return 0, 0, fmt.Errorf("ffprobe não identificou altura ou bitrate")
	}
	return info.Height, info.Bitrate, nil
}

// Inspect reads stream codecs and dimensions for an already validated direct
// file. Callers can reject an obvious teaser/ad without starting an MPV process
// for every search card. If FFprobe is unavailable, callers may retain provider
// metadata and report quality as unknown.
func Inspect(ctx context.Context, stream domain.Stream) (Info, error) {
	path, err := findFFprobe()
	if err != nil {
		return Info{}, err
	}
	ctx, cancel := context.WithTimeout(ctx, 4*time.Second)
	defer cancel()
	args := []string{"-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,bit_rate:format=duration", "-of", "json", "-i", stream.URL}
	if len(stream.Headers) > 0 {
		var headers strings.Builder
		for name, value := range stream.Headers {
			headers.WriteString(name)
			headers.WriteString(": ")
			headers.WriteString(value)
			headers.WriteString("\r\n")
		}
		args = append(args[:len(args)-2], append([]string{"-headers", headers.String()}, args[len(args)-2:]...)...)
	}
	output, err := exec.CommandContext(ctx, path, args...).CombinedOutput()
	if err != nil {
		return Info{}, fmt.Errorf("ffprobe: %w", err)
	}
	return parseProbeInfo(string(output))
}

func findFFprobe() (string, error) {
	if configured := strings.TrimSpace(os.Getenv("ANIMECAOS_FFPROBE_PATH")); configured != "" {
		if info, err := os.Stat(configured); err == nil && !info.IsDir() {
			return configured, nil
		}
		return "", fmt.Errorf("FFprobe configurado não foi encontrado")
	}
	if path, err := exec.LookPath("ffprobe"); err == nil {
		return path, nil
	}
	executable, _ := os.Executable()
	workingDir, _ := os.Getwd()
	name := "ffprobe"
	if runtime.GOOS == "windows" {
		name += ".exe"
	}
	candidates := []string{
		filepath.Join(filepath.Dir(executable), name),
		filepath.Join(filepath.Dir(executable), "bin", name),
		filepath.Join(workingDir, "bin", name),
	}
	for _, candidate := range candidates {
		if info, err := os.Stat(candidate); err == nil && !info.IsDir() {
			return candidate, nil
		}
	}
	return "", fmt.Errorf("FFprobe não está instalado ou configurado")
}

func parseProbeInfo(output string) (Info, error) {
	var result struct {
		Streams []struct {
			CodecType string `json:"codec_type"`
			CodecName string `json:"codec_name"`
			Width     int    `json:"width"`
			Height    int    `json:"height"`
			Bitrate   string `json:"bit_rate"`
		} `json:"streams"`
		Format struct {
			Duration string `json:"duration"`
		} `json:"format"`
	}
	if err := json.Unmarshal([]byte(output), &result); err != nil {
		return Info{}, fmt.Errorf("ffprobe retornou metadados inválidos: %w", err)
	}
	var info Info
	for _, stream := range result.Streams {
		bitrate, _ := strconv.Atoi(stream.Bitrate)
		switch stream.CodecType {
		case "video":
			if info.VideoCodec == "" {
				info.VideoCodec = stream.CodecName
				info.Width, info.Height = stream.Width, stream.Height
				info.Bitrate = bitrate
			}
		case "audio":
			if info.AudioCodec == "" {
				info.AudioCodec = stream.CodecName
			}
		}
	}
	info.Duration, _ = strconv.ParseFloat(result.Format.Duration, 64)
	if info.VideoCodec == "" {
		return info, fmt.Errorf("ffprobe não identificou faixa de vídeo")
	}
	return info, nil
}

func parseProbe(output string) (int, int, error) {
	var height, bitrate int
	for _, line := range strings.Split(output, "\n") {
		key, raw, ok := strings.Cut(strings.TrimSpace(line), "=")
		if !ok {
			continue
		}
		value, err := strconv.Atoi(strings.TrimSpace(raw))
		if err != nil || value <= 0 {
			continue
		}
		switch strings.TrimSpace(key) {
		case "height":
			height = value
		case "bit_rate":
			bitrate = value
		}
	}
	if height == 0 && bitrate == 0 {
		return 0, 0, fmt.Errorf("ffprobe não identificou altura ou bitrate")
	}
	return height, bitrate, nil
}
