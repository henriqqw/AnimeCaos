//go:build !dev

package main

import "testing"

func TestAppInstanceIDUsesProductionNamespace(t *testing.T) {
	if appInstanceID != "com.animecaos.App.production" {
		t.Fatalf("production instance ID = %q", appInstanceID)
	}
}
