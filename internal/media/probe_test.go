package media

import (
	"os"
	"path/filepath"
	"testing"
)

func TestFindFFprobeUsesConfiguredExecutable(t *testing.T) {
	configured := filepath.Join(t.TempDir(), "ffprobe.exe")
	if err := os.WriteFile(configured, []byte("test binary"), 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("ANIMECAOS_FFPROBE_PATH", configured)
	if path, err := findFFprobe(); err != nil || path != configured {
		t.Fatalf("configured FFprobe = %q, %v; want %q", path, err, configured)
	}
}

func TestFindFFprobeRejectsMissingConfiguredExecutable(t *testing.T) {
	t.Setenv("ANIMECAOS_FFPROBE_PATH", filepath.Join(t.TempDir(), "missing.exe"))
	if path, err := findFFprobe(); err == nil || path != "" {
		t.Fatalf("expected missing configured FFprobe to fail, got %q, %v", path, err)
	}
}

func TestParseProbeInfoReadsVideoAndAudioTracks(t *testing.T) {
	info, err := parseProbeInfo(`{"streams":[{"codec_type":"video","codec_name":"h264","width":1920,"height":1080,"bit_rate":"4200000"},{"codec_type":"audio","codec_name":"aac","bit_rate":"192000"}],"format":{"duration":"1260.5"}}`)
	if err != nil {
		t.Fatal(err)
	}
	if info.VideoCodec != "h264" || info.AudioCodec != "aac" || info.Width != 1920 || info.Height != 1080 || info.Bitrate != 4200000 || info.Duration != 1260.5 {
		t.Fatalf("unexpected media info: %+v", info)
	}
}

func TestParseProbeInfoAllowsVideoWithoutAudioForCallerToReject(t *testing.T) {
	info, err := parseProbeInfo(`{"streams":[{"codec_type":"video","codec_name":"vp9","width":320,"height":100}],"format":{"duration":"6.876"}}`)
	if err != nil {
		t.Fatal(err)
	}
	if info.VideoCodec != "vp9" || info.AudioCodec != "" || info.Duration != 6.876 {
		t.Fatalf("unexpected silent clip metadata: %+v", info)
	}
}

func TestParseProbeOutputReadsHeightAndBitrate(t *testing.T) {
	height, bitrate, err := parseProbe("height=1080\nbit_rate=4200000\n")
	if err != nil || height != 1080 || bitrate != 4200000 {
		t.Fatalf("unexpected ffprobe metadata: height=%d bitrate=%d err=%v", height, bitrate, err)
	}
}

func TestParseProbeOutputRejectsMissingMetadata(t *testing.T) {
	if _, _, err := parseProbe("codec_name=h264\nbit_rate=N/A\n"); err == nil {
		t.Fatal("expected missing height and bitrate to be rejected")
	}
}
