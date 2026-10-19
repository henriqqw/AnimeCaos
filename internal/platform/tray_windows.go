package platform

import (
	"runtime"
	"sync"
	"sync/atomic"

	"github.com/getlantern/systray"
)

var (
	trayStartOnce     sync.Once
	trayReadyOnce     sync.Once
	trayReady         = make(chan struct{})
	trayStopRequested atomic.Bool
)

// RunTray starts the Windows notification-area menu on its own locked OS
// thread, keeping it independent from the Wails WebView message loop.
func RunTray(icon []byte, show, minimize, hide, quit func()) {
	trayStartOnce.Do(func() {
		go func() {
			runtime.LockOSThread()
			systray.Run(func() {
				systray.SetIcon(icon)
				systray.SetTooltip("AnimeCaos — abrir, minimizar ou sair")
				openItem := systray.AddMenuItem("Abrir AnimeCaos", "Mostrar a janela do AnimeCaos")
				minimizeItem := systray.AddMenuItem("Minimizar", "Minimizar a janela para a barra de tarefas")
				hideItem := systray.AddMenuItem("Ocultar para bandeja", "Ocultar a janela e mantê-la aberta na bandeja")
				systray.AddSeparator()
				quitItem := systray.AddMenuItem("Sair", "Encerrar o AnimeCaos")
				trayReadyOnce.Do(func() { close(trayReady) })
				if trayStopRequested.Load() {
					systray.Quit()
				}
				go func() {
					for {
						select {
						case <-openItem.ClickedCh:
							show()
						case <-minimizeItem.ClickedCh:
							minimize()
						case <-hideItem.ClickedCh:
							hide()
						case <-quitItem.ClickedCh:
							quit()
							return
						}
					}
				}()
			}, func() {})
		}()
	})
}

// QuitTray removes the notification-area icon and stops its message loop.
func QuitTray() {
	trayStopRequested.Store(true)
	select {
	case <-trayReady:
		systray.Quit()
	default:
	}
}

// TrayAvailable reports whether the Windows notification-area menu finished
// initializing and can safely handle a close-to-tray request.
func TrayAvailable() bool {
	select {
	case <-trayReady:
		return !trayStopRequested.Load()
	default:
		return false
	}
}
