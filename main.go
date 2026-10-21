package main

import (
	"context"
	"embed"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	"github.com/henriqqw/animecaos/internal/app"
	"github.com/henriqqw/animecaos/internal/platform"
	"github.com/henriqqw/animecaos/internal/update"
	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	wr "github.com/wailsapp/wails/v2/pkg/runtime"
)

//go:embed all:frontend/dist
var assets embed.FS

//go:embed assets/icons/icon.ico
var trayIcon []byte

type Desktop struct{ ctx context.Context }

var quitRequested atomic.Bool
var restartRequested atomic.Bool
var startupTopmostMu sync.Mutex
var startupTopmostTimer *time.Timer
var startupTopmostGeneration uint64

const restartAfterExitArg = "--restart-after-exit"
const startupTopmostFailsafe = 30 * time.Second

func writeStartupError(err error) {
	if err == nil {
		return
	}
	_ = os.MkdirAll(platform.DataDir(), 0700)
	_ = os.WriteFile(filepath.Join(platform.DataDir(), "startup-error.log"), []byte(err.Error()), 0600)
	fmt.Fprintln(os.Stderr, err)
}

// runRestartHelper waits outside the Wails process so the previous instance can
// release its single-instance mutex before the app is launched again.
func runRestartHelper() bool {
	if len(os.Args) < 2 || os.Args[1] != restartAfterExitArg {
		return false
	}
	if len(os.Args) < 4 || os.Args[3] != "--" {
		writeStartupError(fmt.Errorf("argumentos inválidos para reiniciar o AnimeCaos"))
		return true
	}
	parentPID, err := strconv.Atoi(os.Args[2])
	if err != nil {
		writeStartupError(fmt.Errorf("PID inválido para reiniciar o AnimeCaos: %w", err))
		return true
	}
	if parentPID <= 0 {
		writeStartupError(fmt.Errorf("PID inválido para reiniciar o AnimeCaos: %q", os.Args[2]))
		return true
	}
	if err := platform.WaitForProcessExit(parentPID); err != nil {
		writeStartupError(fmt.Errorf("não foi possível aguardar o encerramento do AnimeCaos: %w", err))
		return true
	}
	executable, err := os.Executable()
	if err != nil {
		writeStartupError(fmt.Errorf("não foi possível localizar o AnimeCaos para reiniciar: %w", err))
		return true
	}
	command := exec.Command(executable, os.Args[4:]...)
	platform.HideConsole(command)
	if err := command.Start(); err != nil {
		writeStartupError(fmt.Errorf("não foi possível abrir o AnimeCaos novamente: %w", err))
		return true
	}
	_ = command.Process.Release()
	return true
}

func startRestartHelper() error {
	executable, err := os.Executable()
	if err != nil {
		return fmt.Errorf("não foi possível localizar o AnimeCaos para reiniciar: %w", err)
	}
	args := []string{restartAfterExitArg, strconv.Itoa(os.Getpid()), "--"}
	args = append(args, os.Args[1:]...)
	command := exec.Command(executable, args...)
	platform.Hide(command)
	if err := command.Start(); err != nil {
		return fmt.Errorf("não foi possível preparar a reinicialização do AnimeCaos: %w", err)
	}
	_ = command.Process.Release()
	return nil
}

func showMainWindow(ctx context.Context) {
	wr.WindowShow(ctx)
	wr.WindowUnminimise(ctx)
}

func prioritizeStartupWindow(ctx context.Context) {
	wr.WindowSetAlwaysOnTop(ctx, true)
	showMainWindow(ctx)
	startupTopmostMu.Lock()
	if startupTopmostTimer != nil {
		startupTopmostTimer.Stop()
	}
	startupTopmostGeneration++
	generation := startupTopmostGeneration
	var timer *time.Timer
	timer = time.AfterFunc(startupTopmostFailsafe, func() {
		startupTopmostMu.Lock()
		defer startupTopmostMu.Unlock()
		if generation != startupTopmostGeneration || startupTopmostTimer != timer {
			return
		}
		startupTopmostTimer = nil
		if ctx.Err() == nil {
			wr.WindowSetAlwaysOnTop(ctx, false)
		}
	})
	startupTopmostTimer = timer
	startupTopmostMu.Unlock()
}

func showMainWindowWithSplash(ctx context.Context) {
	prioritizeStartupWindow(ctx)
	wr.WindowReloadApp(ctx)
}

func restartFromTray(ctx context.Context) {
	if developmentBuild {
		// Keep the Wails dev process and its Vite server alive. Restarting the
		// compiled child executable directly would leave it pointing at a Vite
		// server that the wails dev command shuts down with the parent process.
		showMainWindowWithSplash(ctx)
		return
	}
	quitRequested.Store(true)
	restartRequested.Store(true)
	platform.QuitTray()
	wr.Quit(ctx)
}

func stopStartupTopmostTimer() {
	startupTopmostMu.Lock()
	if startupTopmostTimer != nil {
		startupTopmostTimer.Stop()
		startupTopmostTimer = nil
	}
	startupTopmostMu.Unlock()
}

func saveWindowGeometry(ctx context.Context, service *app.Service) {
	if wr.WindowIsMinimised(ctx) {
		return
	}
	width, height := wr.WindowGetSize(ctx)
	x, y := wr.WindowGetPosition(ctx)
	if width < 800 || height < 560 || !platform.WindowPositionVisible(x, y, width, height) {
		return
	}
	settings := service.Settings()
	settings.Width, settings.Height = width, height
	settings.X, settings.Y = x, y
	_ = service.SaveSettings(settings)
}

func (d *Desktop) ChooseDirectory() (string, error) {
	return wr.OpenDirectoryDialog(d.ctx, wr.OpenDialogOptions{Title: "Pasta de downloads"})
}
func (d *Desktop) ChoosePlayer() (string, error) {
	return wr.OpenFileDialog(d.ctx, wr.OpenDialogOptions{Title: "Executável do player"})
}
func (d *Desktop) OpenLink(url string) error { wr.BrowserOpenURL(d.ctx, url); return nil }
func (d *Desktop) StartupSplashToken() uint64 {
	startupTopmostMu.Lock()
	defer startupTopmostMu.Unlock()
	return startupTopmostGeneration
}

func (d *Desktop) StartupSplashFinished(token uint64) {
	if d.ctx == nil {
		return
	}
	startupTopmostMu.Lock()
	if token != startupTopmostGeneration {
		startupTopmostMu.Unlock()
		return
	}
	if startupTopmostTimer != nil {
		startupTopmostTimer.Stop()
		startupTopmostTimer = nil
	}
	wr.WindowSetAlwaysOnTop(d.ctx, false)
	startupTopmostMu.Unlock()
}

func main() {
	if runRestartHelper() {
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "--apply-update" {
		f := flag.NewFlagSet("update", flag.ContinueOnError)
		pkg := f.String("apply-update", "", "")
		target := f.String("target", "", "")
		parent := f.Int("parent", 0, "")
		if e := f.Parse(os.Args[1:]); e != nil {
			return
		}
		if e := update.RunHelper(*pkg, *target, *parent); e != nil {
			os.WriteFile(filepath.Join(filepath.Dir(os.Args[0]), "updater-error.log"), []byte(e.Error()), 0600)
		}
		return
	}
	var desktop Desktop
	webviewOptions, e := platform.WebViewOptions()
	if e != nil {
		writeStartupError(e)
		return
	}
	service, e := app.New(context.Background(), platform.DataDir(), func(name string, data any) {
		if desktop.ctx != nil {
			if name == "quit" {
				quitRequested.Store(true)
				platform.QuitTray()
				wr.Quit(desktop.ctx)
				return
			}
			wr.EventsEmit(desktop.ctx, name, data)
		}
	})
	if e != nil {
		fmt.Fprintln(os.Stderr, e)
		return
	}
	defer func() {
		service.Close()
		if restartRequested.Load() {
			writeStartupError(startRestartHelper())
		}
	}()
	settings := service.Settings()
	e = wails.Run(&options.App{Title: "AnimeCaos", Width: max(900, settings.Width), Height: max(600, settings.Height), MinWidth: 800, MinHeight: 560, BackgroundColour: options.NewRGB(0, 0, 0), AssetServer: &assetserver.Options{Assets: assets}, Bind: []interface{}{service, &desktop}, Windows: webviewOptions,
		OnStartup: func(ctx context.Context) {
			desktop.ctx = ctx
			width, height := max(900, settings.Width), max(600, settings.Height)
			if (settings.X != 0 || settings.Y != 0) && platform.WindowPositionVisible(settings.X, settings.Y, width, height) {
				wr.WindowSetPosition(ctx, settings.X, settings.Y)
			} else {
				wr.WindowCenter(ctx)
			}
			prioritizeStartupWindow(ctx)
			platform.RunTray(trayIcon, func() { showMainWindow(ctx) }, func() { wr.WindowMinimise(ctx) }, func() { wr.WindowHide(ctx) }, func() {
				restartFromTray(ctx)
			}, func() {
				quitRequested.Store(true)
				platform.QuitTray()
				wr.Quit(ctx)
			})
			if !developmentBuild {
				service.StartStartupAutoUpdate()
			}
		},
		OnBeforeClose: func(ctx context.Context) bool {
			saveWindowGeometry(ctx, service)
			if quitRequested.Load() {
				return false
			}
			if !platform.TrayAvailable() {
				return false
			}
			wr.WindowHide(ctx)
			return true
		},
		OnShutdown: func(context.Context) {
			stopStartupTopmostTimer()
			platform.QuitTray()
		},
		SingleInstanceLock: &options.SingleInstanceLock{UniqueId: appInstanceID, OnSecondInstanceLaunch: func(options.SecondInstanceData) {
			if desktop.ctx != nil {
				showMainWindowWithSplash(desktop.ctx)
			}
		}},
	})
	if e != nil {
		writeStartupError(e)
	}
}
