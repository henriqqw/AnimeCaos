//go:build !windows

package platform

import "github.com/wailsapp/wails/v2/pkg/options/windows"

func WebViewOptions() (*windows.Options, error) { return nil, nil }
