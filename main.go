package main

import (
	"context"
	"embed"
	"flag"
	"fmt"
	"github.com/henriqqw/animecaos/internal/app"
	"github.com/henriqqw/animecaos/internal/platform"
	"github.com/henriqqw/animecaos/internal/update"
	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	wr "github.com/wailsapp/wails/v2/pkg/runtime"
	"os"
	"path/filepath"
)

//go:embed all:frontend/dist
var assets embed.FS

type Desktop struct{ ctx context.Context }

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
	service, e := app.New(context.Background(), platform.DataDir(), func(name string, data any) {
		if desktop.ctx != nil {
			if name == "quit" {
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
	e = wails.Run(&options.App{Title: "AnimeCaos", Width: max(900, settings.Width), Height: max(600, settings.Height), MinWidth: 800, MinHeight: 560, BackgroundColour: options.NewRGB(18, 20, 28), AssetServer: &assetserver.Options{Assets: assets}, Bind: []interface{}{service, &desktop},
		OnStartup: func(ctx context.Context) {
			desktop.ctx = ctx
			if settings.X != 0 || settings.Y != 0 {
				wr.WindowSetPosition(ctx, settings.X, settings.Y)
			}
		},
		OnBeforeClose: func(ctx context.Context) bool {
			v := service.Settings()
			v.Width, v.Height = wr.WindowGetSize(ctx)
			v.X, v.Y = wr.WindowGetPosition(ctx)
			service.SaveSettings(v)
			return false
		},
		SingleInstanceLock: &options.SingleInstanceLock{UniqueId: "com.animecaos.App", OnSecondInstanceLaunch: func(options.SecondInstanceData) {
			if desktop.ctx != nil {
				wr.WindowShow(desktop.ctx)
			}
		}},
	})
	if e != nil {
		os.MkdirAll(platform.DataDir(), 0700)
		os.WriteFile(filepath.Join(platform.DataDir(), "startup-error.log"), []byte(e.Error()), 0600)
		fmt.Fprintln(os.Stderr, e)
	}
}
