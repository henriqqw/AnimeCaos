// animecaos is the terminal client for the same services used by Wails.
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"github.com/henriqqw/animecaos/internal/app"
	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/platform"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"time"
)

func main() {
	if e := run(); e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
}
func run() error {
	command := "interactive"
	args := os.Args[1:]
	if len(args) > 0 && !strings.HasPrefix(args[0], "-") {
		command = args[0]
		args = args[1:]
	}
	f := flag.NewFlagSet("animecaos "+command, flag.ContinueOnError)
	query := f.String("query", "", "título para pesquisa")
	id := f.String("id", "", "ID do anime ou mangá")
	provider := f.String("provider", "animefire", "fonte")
	page := f.Int("page", 1, "página da busca")
	episode := f.String("episode", "", "ID do episódio")
	data := f.String("data", platform.DataDir(), "diretório de dados")
	resume := f.Bool("continue", false, "continuar pelo histórico")
	if e := f.Parse(args); e != nil {
		return e
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	events := make(chan app.PlayerEvent, 32)
	s, e := app.New(ctx, *data, func(name string, v any) {
		if name == "player" {
			p := v.(app.PlayerEvent)
			if !p.State.Playing {
				select {
				case events <- p:
				default:
				}
			}
		}
		if name == "error" {
			fmt.Fprintln(os.Stderr, v)
		}
	})
	if e != nil {
		return e
	}
	defer s.Close()
	output := func(v any, e error) error {
		if e != nil {
			return e
		}
		encoder := json.NewEncoder(os.Stdout)
		encoder.SetIndent("", "  ")
		return encoder.Encode(v)
	}
	switch command {
	case "doctor":
		return output(s.Diagnose(), nil)
	case "search":
		r, e := s.Search("cli", *query, *page, nil)
		return output(r, e)
	case "details":
		d, e := s.Details("cli", domain.Anime{ID: *id, URL: *id, Provider: *provider})
		return output(d, e)
	case "history":
		r, e := s.History()
		return output(r, e)
	case "list":
		r, e := s.Library()
		return output(r, e)
	case "files":
		r, e := s.LocalFiles()
		return output(r, e)
	case "manga":
		r, e := s.MangaSearch("cli", *query)
		return output(r, e)
	case "chapters":
		r, e := s.Chapters("cli", *id)
		return output(r, e)
	case "accounts":
		return output(s.Accounts(), nil)
	case "login":
		return s.Login("cli", *provider)
	case "update":
		r, e := s.CheckUpdate("cli")
		return output(r, e)
	case "play", "download":
		d, e := s.Details("cli", domain.Anime{ID: *id, URL: *id, Provider: *provider})
		if e != nil {
			return e
		}
		index := -1
		for i, ep := range d.Episodes {
			if ep.ID == *episode {
				index = i
				break
			}
		}
		if index < 0 {
			return fmt.Errorf("escolha --episode com um ID retornado por details")
		}
		if command == "play" {
			if e = s.Play("cli", d.Anime, []domain.Episode{d.Episodes[index]}, 0, true); e != nil {
				return e
			}
			select {
			case <-ctx.Done():
				return ctx.Err()
			case p := <-events:
				if p.State.Error != "" {
					return fmt.Errorf("%s", p.State.Error)
				}
				return nil
			}
		}
		jobs, e := s.Enqueue(d.Anime, []domain.Episode{d.Episodes[index]})
		if e != nil {
			return e
		}
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-ticker.C:
				for _, j := range s.Downloads() {
					if j.ID != jobs[0].ID {
						continue
					}
					fmt.Fprintf(os.Stderr, "%s %.1f%% %s %s\n", j.Status, j.Percent, j.Speed, j.ETA)
					if j.Status == "done" {
						return output(j, nil)
					}
					if j.Status == "failed" || j.Status == "cancelled" {
						return fmt.Errorf("%s", j.Error)
					}
				}
			}
		}
	case "interactive":
		return interactive(ctx, s, *query, *resume, events)
	default:
		return fmt.Errorf("comandos: interactive, doctor, search, details, play, download, history, list, files, manga, chapters, accounts, login, update")
	}
}
func interactive(ctx context.Context, s *app.Service, query string, resume bool, events <-chan app.PlayerEvent) error {
	reader := bufio.NewScanner(os.Stdin)
	choose := func(labels []string) (int, error) {
		for i, v := range labels {
			fmt.Printf("%d. %s\n", i+1, v)
		}
		fmt.Println("0. Sair")
		for reader.Scan() {
			n, e := strconv.Atoi(strings.TrimSpace(reader.Text()))
			if e == nil && n == 0 {
				return -1, nil
			}
			if e == nil && n > 0 && n <= len(labels) {
				return n - 1, nil
			}
			fmt.Println("Digite o número da opção.")
		}
		return -1, reader.Err()
	}
	var a domain.Anime
	var previous domain.History
	if resume {
		h, e := s.History()
		if e != nil {
			return e
		}
		labels := []string{}
		for _, v := range h {
			labels = append(labels, v.Anime.Title)
		}
		i, e := choose(labels)
		if e != nil || i < 0 {
			return e
		}
		previous = h[i]
		a = previous.Anime
	} else {
		if query == "" {
			fmt.Println("Pesquise anime:")
			if !reader.Scan() {
				return reader.Err()
			}
			query = reader.Text()
		}
		r, e := s.Search("cli", query, 1, nil)
		if e != nil {
			return e
		}
		labels := []string{}
		for _, v := range r.Items {
			labels = append(labels, v.Title)
		}
		i, e := choose(labels)
		if e != nil || i < 0 {
			return e
		}
		a = r.Items[i]
	}
	d, e := s.Details("cli", a)
	if e != nil {
		return e
	}
	index := -1
	if resume && !previous.NeedsResolve {
		for i, ep := range d.Episodes {
			if ep.Key() == previous.Episode.Key() {
				index = i
				break
			}
		}
	}
	if index < 0 {
		labels := []string{}
		for _, ep := range d.Episodes {
			labels = append(labels, fmt.Sprintf("T%d · Ep. %g · %s", ep.Season, ep.Number, ep.Title))
		}
		index, e = choose(labels)
		if e != nil || index < 0 {
			return e
		}
	}
	for {
		if e = s.Play("cli", d.Anime, []domain.Episode{d.Episodes[index]}, 0, true); e != nil {
			return e
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case p := <-events:
			if p.State.Error != "" {
				fmt.Fprintln(os.Stderr, p.State.Error)
			}
			if p.State.EOF && s.Settings().Autoplay && index+1 < len(d.Episodes) {
				index++
				continue
			}
		}
		labels := []string{}
		deltas := []int{}
		if index+1 < len(d.Episodes) {
			labels = append(labels, "Próximo")
			deltas = append(deltas, 1)
		}
		if index > 0 {
			labels = append(labels, "Anterior")
			deltas = append(deltas, -1)
		}
		i, e := choose(labels)
		if e != nil || i < 0 {
			return e
		}
		index += deltas[i]
	}
}
