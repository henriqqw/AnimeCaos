package platform

import "os"

// Publish atomically installs a complete file without replacing an existing
// destination. Temporary and final files must share the same filesystem.
func Publish(temp, destination string) error {
	if e := os.Link(temp, destination); e != nil {
		return e
	}
	return os.Remove(temp)
}
