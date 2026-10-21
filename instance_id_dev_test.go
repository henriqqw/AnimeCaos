//go:build dev

package main

import "testing"

func TestAppInstanceIDUsesDevelopmentNamespace(t *testing.T) {
	if appInstanceID != "com.animecaos.App.dev" {
		t.Fatalf("development instance ID = %q", appInstanceID)
	}
	if !developmentBuild {
		t.Fatal("development build must reload the existing Wails process when restarting from the tray")
	}
}
