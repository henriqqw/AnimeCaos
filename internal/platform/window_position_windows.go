package platform

import (
	"runtime"
	"unsafe"

	"golang.org/x/sys/windows"
)

type monitorInfo struct {
	cbSize    uint32
	rcMonitor rect
	rcWork    rect
	dwFlags   uint32
}

type rect struct {
	left, top, right, bottom int32
}

var (
	user32WindowPosition = windows.NewLazySystemDLL("user32.dll")
	enumDisplayMonitors  = user32WindowPosition.NewProc("EnumDisplayMonitors")
	getMonitorInfo       = user32WindowPosition.NewProc("GetMonitorInfoW")
)

// WindowPositionVisible checks all Windows work areas, including monitors with
// negative desktop coordinates, before applying a persisted window position.
func WindowPositionVisible(x, y, width, height int) bool {
	if width <= 0 || height <= 0 {
		return false
	}
	found := false
	callback := func(monitor, _, _, _ uintptr) uintptr {
		info := monitorInfo{cbSize: uint32(unsafe.Sizeof(monitorInfo{}))}
		ok, _, _ := getMonitorInfo.Call(monitor, uintptr(unsafe.Pointer(&info)))
		if ok != 0 && windowPositionIntersectsWorkArea(x, y, width, height, workArea{
			left: int(info.rcWork.left), top: int(info.rcWork.top), right: int(info.rcWork.right), bottom: int(info.rcWork.bottom),
		}) {
			found = true
		}
		return 1
	}
	callbackPtr := windows.NewCallback(callback)
	result, _, _ := enumDisplayMonitors.Call(0, 0, callbackPtr, 0)
	runtime.KeepAlive(callback)
	return result != 0 && found
}
