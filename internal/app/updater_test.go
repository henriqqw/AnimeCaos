package app

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestStartupUpdateTargetOnlyAllowsSupportedPackagedInstalls(t *testing.T) {
	root := t.TempDir()
	executable := filepath.Join(root, "AnimeCaos.exe")
	if _, ok := startupUpdateTarget("windows", executable, "", ""); ok {
		t.Fatal("Windows build without a release manifest is eligible for startup update")
	}
	if err := os.WriteFile(filepath.Join(root, "release-manifest.json"), []byte(`{"version":"3.0.0"}`), 0600); err != nil {
		t.Fatal(err)
	}
	if target, ok := startupUpdateTarget("windows", executable, "", ""); !ok || target != root {
		t.Fatalf("Windows packaged target = %q, supported=%v", target, ok)
	}

	appImage := filepath.Join(root, "AnimeCaos.AppImage")
	if target, ok := startupUpdateTarget("linux", executable, appImage, ""); !ok || target != appImage {
		t.Fatalf("AppImage target = %q, supported=%v", target, ok)
	}
	if _, ok := startupUpdateTarget("linux", executable, appImage, "org.example.AnimeCaos"); ok {
		t.Fatal("Flatpak must remain managed by the system package manager")
	}
	if _, ok := startupUpdateTarget("linux", executable, "", ""); ok {
		t.Fatal("Linux build without APPIMAGE must not replace an arbitrary executable")
	}
	if _, ok := startupUpdateTarget("darwin", executable, appImage, ""); ok {
		t.Fatal("unsupported platform is eligible for startup update")
	}
}

func TestStartupAutoUpdateFinishesWhenCurrentReleaseIsLatest(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"tag_name": "v3.0.0", "assets": []any{}})
	}))
	defer server.Close()

	s, err := New(context.Background(), t.TempDir(), nil)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	s.updater.API = server.URL
	s.updater.Client.HTTP = server.Client()

	s.runStartupAutoUpdate()
	if status := s.StartupUpdateStatus(); !status.Done || status.State != "ready" || status.Percent != 100 {
		t.Fatalf("startup update status = %+v", status)
	}
}

func TestStartupAutoUpdateFailsOpenWhenReleaseCheckFails(t *testing.T) {
	server := httptest.NewServer(http.NotFoundHandler())
	defer server.Close()

	s, err := New(context.Background(), t.TempDir(), nil)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	s.updater.API = server.URL
	s.updater.Client.HTTP = server.Client()

	s.runStartupAutoUpdate()
	if status := s.StartupUpdateStatus(); !status.Done || status.State != "failed" {
		t.Fatalf("failed update check kept startup blocked: %+v", status)
	}
}
