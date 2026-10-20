package main

import (
	"context"
	"embed"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sync/atomic"

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

func showMainWindow(ctx context.Context) {
	wr.WindowShow(ctx)
	wr.WindowUnminimise(ctx)
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

func main() {
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
		_ = os.MkdirAll(platform.DataDir(), 0700)
		_ = os.WriteFile(filepath.Join(platform.DataDir(), "startup-error.log"), []byte(e.Error()), 0600)
		fmt.Fprintln(os.Stderr, e)
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
	defer service.Close()
	settings := service.Settings()
	e = wails.Run(&options.App{Title: "AnimeCaos", Width: max(900, settings.Width), Height: max(600, settings.Height), MinWidth: 800, MinHeight: 560, BackgroundColour: options.NewRGB(18, 20, 28), AssetServer: &assetserver.Options{Assets: assets}, Bind: []interface{}{service, &desktop}, Windows: webviewOptions,
		OnStartup: func(ctx context.Context) {
			desktop.ctx = ctx
			width, height := max(900, settings.Width), max(600, settings.Height)
			if (settings.X != 0 || settings.Y != 0) && platform.WindowPositionVisible(settings.X, settings.Y, width, height) {
				wr.WindowSetPosition(ctx, settings.X, settings.Y)
			} else {
				wr.WindowCenter(ctx)
			}
			platform.RunTray(trayIcon, func() { showMainWindow(ctx) }, func() { wr.WindowMinimise(ctx) }, func() { wr.WindowHide(ctx) }, func() {
				quitRequested.Store(true)
				platform.QuitTray()
				wr.Quit(ctx)
			})
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
		OnShutdown: func(context.Context) { platform.QuitTray() },
		SingleInstanceLock: &options.SingleInstanceLock{UniqueId: appInstanceID, OnSecondInstanceLaunch: func(options.SecondInstanceData) {
			if desktop.ctx != nil {
				showMainWindow(desktop.ctx)
			}
		}},
	})
	if e != nil {
		os.MkdirAll(platform.DataDir(), 0700)
		os.WriteFile(filepath.Join(platform.DataDir(), "startup-error.log"), []byte(e.Error()), 0600)
		fmt.Fprintln(os.Stderr, e)
	}
}
