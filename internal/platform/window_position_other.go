//go:build !windows

package platform

// WindowPositionVisible rejects invalid and minimized coordinates on systems
// where the native display work areas are not queried by this platform layer.
func WindowPositionVisible(x, y, width, height int) bool {
	return width > 0 && height > 0 && x > -16000 && y > -16000
}
