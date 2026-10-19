//go:build !windows

package platform

// RunTray currently adds a notification-area menu only on Windows.
func RunTray(_ []byte, _, _, _, _ func()) {}

// QuitTray is a no-op on platforms without the Windows notification-area menu.
func QuitTray() {}

// TrayAvailable reports that this platform has no tray menu adapter.
func TrayAvailable() bool { return false }
