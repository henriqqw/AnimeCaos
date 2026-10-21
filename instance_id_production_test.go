//go:build !dev

package main

import "testing"

func TestAppInstanceIDUsesProductionNamespace(t *testing.T) {
	if appInstanceID != "com.animecaos.App.production" {
		t.Fatalf("production instance ID = %q", appInstanceID)
	}
	if developmentBuild {
		t.Fatal("production build must relaunch the executable when restarting from the tray")
	}
}
