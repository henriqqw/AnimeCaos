//go:build windows

package platform

import (
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

var user32 = windows.NewLazySystemDLL("user32.dll")
var getWindowText = user32.NewProc("GetWindowTextW")
var showWindow = user32.NewProc("ShowWindow")
var setForegroundWindow = user32.NewProc("SetForegroundWindow")
var allowSetForegroundWindow = user32.NewProc("AllowSetForegroundWindow")
var getWindowThreadProcessID = user32.NewProc("GetWindowThreadProcessId")
var attachThreadInput = user32.NewProc("AttachThreadInput")
var bringWindowToTop = user32.NewProc("BringWindowToTop")
var getForegroundWindow = user32.NewProc("GetForegroundWindow")

func revealFileNative(target string) error {
	folder := filepath.Dir(target)
	if hwnd := findExplorerFolder(filepath.Base(folder)); hwnd != 0 {
		return activateExplorerFolder(hwnd)
	}

	// The caller is foreground after a direct button click. Granting Explorer
	// foreground permission lets its existing shell process show the window.
	_, _, _ = allowSetForegroundWindow.Call(^uintptr(0))

	command := exec.Command("explorer.exe", folder)
	if err := command.Start(); err != nil {
		return fmt.Errorf("não foi possível abrir a pasta do arquivo: %w", err)
	}
	go command.Wait()

	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if hwnd := findExplorerFolder(filepath.Base(folder)); hwnd != 0 {
			return activateExplorerFolder(hwnd)
		}
		time.Sleep(75 * time.Millisecond)
	}
	return fmt.Errorf("o Explorador não exibiu a pasta %q", filepath.Base(folder))
}

func findExplorerFolder(folderName string) windows.HWND {
	var found windows.HWND
	callback := windows.NewCallback(func(hwnd windows.HWND, _ uintptr) uintptr {
		if !windows.IsWindowVisible(hwnd) {
			return 1
		}
		var className [128]uint16
		classLen, err := windows.GetClassName(hwnd, &className[0], int32(len(className)))
		if err != nil || windows.UTF16ToString(className[:classLen]) != "CabinetWClass" {
			return 1
		}

		var title [512]uint16
		length, _, _ := getWindowText.Call(uintptr(hwnd), uintptr(unsafe.Pointer(&title[0])), uintptr(len(title)))
		windowTitle := windows.UTF16ToString(title[:length])
		if strings.EqualFold(windowTitle, folderName) || strings.HasPrefix(strings.ToLower(windowTitle), strings.ToLower(folderName)+" - ") {
			found = hwnd
			return 0
		}
		return 1
	})
	_ = windows.EnumWindows(callback, nil)
	return found
}

func activateExplorerFolder(hwnd windows.HWND) error {
	_, _, _ = showWindow.Call(uintptr(hwnd), 9) // SW_RESTORE
	var processID uint32
	targetThread, _, _ := getWindowThreadProcessID.Call(uintptr(hwnd), uintptr(unsafe.Pointer(&processID)))
	_, _, _ = allowSetForegroundWindow.Call(uintptr(processID))
	foreground, _, _ := getForegroundWindow.Call()
	foregroundThread, _, _ := getWindowThreadProcessID.Call(foreground, 0)
	attached, _, _ := attachThreadInput.Call(foregroundThread, targetThread, 1)
	if attached != 0 {
		defer attachThreadInput.Call(foregroundThread, targetThread, 0)
	}
	_, _, _ = bringWindowToTop.Call(uintptr(hwnd))
	result, _, _ := setForegroundWindow.Call(uintptr(hwnd))
	if result == 0 && windows.GetForegroundWindow() != hwnd {
		return fmt.Errorf("o Windows recusou trazer a pasta para frente")
	}
	return nil
}
