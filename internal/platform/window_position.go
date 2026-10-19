package platform

type workArea struct {
	left, top, right, bottom int
}

// windowPositionIntersectsWorkArea requires a useful part of the title bar to
// stay on-screen so a saved window can always be recovered with the mouse.
func windowPositionIntersectsWorkArea(x, y, width, height int, area workArea) bool {
	if width <= 0 || height <= 0 || area.right <= area.left || area.bottom <= area.top {
		return false
	}
	visibleLeft := max(x, area.left)
	visibleRight := min(x+width, area.right)
	titleBottom := y + min(height, 96)
	visibleTop := max(y, area.top)
	visibleBottom := min(titleBottom, area.bottom)
	return visibleRight-visibleLeft >= min(width, 160) && visibleBottom-visibleTop >= min(height, 48)
}
