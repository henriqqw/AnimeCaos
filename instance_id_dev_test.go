//go:build dev

package main

import "testing"

func TestAppInstanceIDUsesDevelopmentNamespace(t *testing.T) {
	if appInstanceID != "com.animecaos.App.dev" {
		t.Fatalf("development instance ID = %q", appInstanceID)
	}
}
