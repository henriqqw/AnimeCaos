package integrations

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/platform"
	"github.com/henriqqw/animecaos/internal/securestore"
	"github.com/henriqqw/animecaos/internal/store"
)

const MALClientID = "62b4b2a8de68653e14c06d37e3a43fda"
const AniListClientID = "39400"
const DiscordClientID = "1494706525426421760"
const defaultMALOAuthBase = "https://myanimelist.net/v1/oauth2"
const defaultMALAPIBase = "https://api.myanimelist.net/v2"
const defaultDiscordOAuthBase = "https://discord.com/api/oauth2"
const defaultDiscordAuthorizeURL = "https://discord.com/oauth2/authorize"
const defaultDiscordAPIBase = "https://discord.com/api/v10"
const defaultDiscordListenAddr = "127.0.0.1:9744"
const defaultDiscordRedirectURI = "http://127.0.0.1:9744/"
const malClientSecretKey = "mal-client-secret"

type Token struct {
	Access  string `json:"accessToken"`
	Refresh string `json:"refreshToken"`
	Expires int64  `json:"expiresAt"`
}
type Account struct {
	Provider   string `json:"provider"`
	Connected  bool   `json:"connected"`
	ID         int    `json:"id"`
	ExternalID string `json:"externalId,omitempty"`
	Name       string `json:"name"`
	Avatar     string `json:"avatar"`
	AnimeCount int    `json:"animeCount"`
	Episodes   int    `json:"episodes"`
	Minutes    int    `json:"minutes"`
	Error      string `json:"error"`
}
type Accounts struct {
	Store               *store.Store
	Meta                *Metadata
	Client              *netx.Client
	MALGate             *netx.Gate
	Credentials         securestore.Store
	MALOAuthBase        string
	MALAPIBase          string
	DiscordOAuthBase    string
	DiscordAuthorizeURL string
	DiscordAPIBase      string
	DiscordListenAddr   string
	DiscordRedirectURI  string
	login               sync.Mutex
	refresh             sync.Mutex
	syncMu              sync.Mutex
	Open                func(string) error
}

func NewAccounts(s *store.Store, m *Metadata) *Accounts {
	return NewAccountsWithCredentials(s, m, securestore.System{})
}

// NewAccountsWithCredentials allows tests to use an isolated in-memory vault.
func NewAccountsWithCredentials(s *store.Store, m *Metadata, credentials securestore.Store) *Accounts {
	malGate := &netx.Gate{Interval: time.Second}
	if m != nil && m.MAL != nil && m.MAL.Gate != nil {
		malGate = m.MAL.Gate
	}
	return &Accounts{Store: s, Meta: m, Client: m.Client, MALGate: malGate, Credentials: credentials, MALOAuthBase: defaultMALOAuthBase, MALAPIBase: defaultMALAPIBase, DiscordOAuthBase: defaultDiscordOAuthBase, DiscordAuthorizeURL: defaultDiscordAuthorizeURL, DiscordAPIBase: defaultDiscordAPIBase, DiscordListenAddr: defaultDiscordListenAddr, DiscordRedirectURI: defaultDiscordRedirectURI, Open: platform.Open}
}

func (a *Accounts) clearLegacyCredential(key string) error {
	var raw json.RawMessage
	err := a.Store.Get("auth", key, &raw)
	if errors.Is(err, sql.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	return a.Store.DeleteSensitive("auth", key)
}

func (a *Accounts) readCredential(vaultKey, legacyKey string, dst any) error {
	raw, err := a.Credentials.Get(vaultKey)
	if err == nil {
		if err = json.Unmarshal([]byte(raw), dst); err != nil {
			return fmt.Errorf("credencial inválida no cofre seguro: %w", err)
		}
		if legacyKey != "" {
			if err = a.clearLegacyCredential(legacyKey); err != nil {
				return fmt.Errorf("a credencial está no cofre seguro, mas a cópia antiga não pôde ser removida: %w", err)
			}
		}
		return nil
	}
	if !securestore.IsNotFound(err) {
		return fmt.Errorf("não foi possível acessar o cofre seguro do sistema: %w", err)
	}
	if legacyKey == "" {
		return securestore.ErrNotFound
	}
	if err = a.Store.Get("auth", legacyKey, dst); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return securestore.ErrNotFound
		}
		return err
	}
	encoded, err := json.Marshal(dst)
	if err != nil {
		return err
	}
	if err = a.Credentials.Set(vaultKey, string(encoded)); err != nil {
		return fmt.Errorf("não foi possível migrar a credencial para o cofre seguro; a cópia local foi preservada: %w", err)
	}
	if err = a.clearLegacyCredential(legacyKey); err != nil {
		return fmt.Errorf("a credencial foi migrada, mas a cópia antiga não pôde ser removida: %w", err)
	}
	return nil
}

func (a *Accounts) writeCredential(vaultKey, legacyKey string, value any) error {
	encoded, err := json.Marshal(value)
	if err != nil {
		return err
	}
	if err = a.Credentials.Set(vaultKey, string(encoded)); err != nil {
		return fmt.Errorf("não foi possível salvar no cofre seguro do sistema: %w", err)
	}
	if legacyKey != "" {
		if err = a.clearLegacyCredential(legacyKey); err != nil {
			return fmt.Errorf("o valor está no cofre seguro, mas a cópia antiga não pôde ser removida: %w", err)
		}
	}
	return nil
}

func (a *Accounts) deleteCredential(vaultKey, legacyKey string) error {
	vaultErr := a.Credentials.Delete(vaultKey)
	if securestore.IsNotFound(vaultErr) {
		vaultErr = nil
	}
	var legacyErr error
	if legacyKey != "" {
		legacyErr = a.clearLegacyCredential(legacyKey)
	}
	return errors.Join(vaultErr, legacyErr)
}

func (a *Accounts) malOAuthBase() string {
	if base := strings.TrimRight(a.MALOAuthBase, "/"); base != "" {
		return base
	}
	return defaultMALOAuthBase
}

func (a *Accounts) malAPIBase() string {
	if base := strings.TrimRight(a.MALAPIBase, "/"); base != "" {
		return base
	}
	return defaultMALAPIBase
}

func (a *Accounts) discordOAuthBase() string {
	if base := strings.TrimRight(a.DiscordOAuthBase, "/"); base != "" {
		return base
	}
	return defaultDiscordOAuthBase
}

func (a *Accounts) discordAPIBase() string {
	if base := strings.TrimRight(a.DiscordAPIBase, "/"); base != "" {
		return base
	}
	return defaultDiscordAPIBase
}

func (a *Accounts) discordAuthorizeURL() string {
	if base := strings.TrimSpace(a.DiscordAuthorizeURL); base != "" {
		return base
	}
	return defaultDiscordAuthorizeURL
}

func (a *Accounts) discordListenAddr() string {
	if addr := strings.TrimSpace(a.DiscordListenAddr); addr != "" {
		return addr
	}
	return defaultDiscordListenAddr
}

func (a *Accounts) discordRedirectURI() string {
	if redirect := strings.TrimSpace(a.DiscordRedirectURI); redirect != "" {
		return redirect
	}
	return defaultDiscordRedirectURI
}

func (a *Accounts) MALClientSecretConfigured() (bool, error) {
	var secret string
	err := a.readCredential("mal-client-secret", malClientSecretKey, &secret)
	if securestore.IsNotFound(err) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return secret != "", nil
}

func (a *Accounts) SetMALClientSecret(secret string) error {
	secret = strings.TrimSpace(secret)
	if len(secret) > 4096 {
		return fmt.Errorf("Client Secret do MyAnimeList excede o limite permitido")
	}
	if secret == "" {
		return a.deleteCredential("mal-client-secret", malClientSecretKey)
	}
	return a.writeCredential("mal-client-secret", malClientSecretKey, secret)
}

func (a *Accounts) malClientSecret() (string, error) {
	var secret string
	err := a.readCredential("mal-client-secret", malClientSecretKey, &secret)
	if securestore.IsNotFound(err) {
		return "", nil
	}
	return secret, err
}
func random() string {
	var b [48]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	return base64.RawURLEncoding.EncodeToString(b[:])
}

func pkceChallenge(verifier string) string {
	sum := sha256.Sum256([]byte(verifier))
	return base64.RawURLEncoding.EncodeToString(sum[:])
}

func (a *Accounts) Login(ctx context.Context, provider, malID string) (resultErr error) {
	if !a.login.TryLock() {
		return fmt.Errorf("já existe um login em andamento")
	}
	defer a.login.Unlock()
	if provider == "discord" {
		return a.loginDiscord(ctx)
	}
	if provider != "anilist" && provider != "mal" {
		return fmt.Errorf("integração desconhecida")
	}
	port := "9742"
	redirect := "http://localhost:9742"
	if provider == "mal" {
		port = "9743"
		redirect = "http://localhost:9743/"
		if malID == "" {
			return fmt.Errorf("configure o Client ID do MyAnimeList")
		}
	}
	listener, e := net.Listen("tcp4", "127.0.0.1:"+port)
	if e != nil {
		return fmt.Errorf("não foi possível iniciar retorno do login na porta %s: %w", port, e)
	}
	ctx, cancel := context.WithTimeout(ctx, 2*time.Minute)
	defer cancel()
	state := random()
	verifier := random()
	received := make(chan string, 1)
	finished := make(chan struct{})
	complete := func(w http.ResponseWriter, r *http.Request) bool {
		select {
		case <-finished:
			if resultErr != nil {
				http.Error(w, "Não foi possível conectar: "+resultErr.Error(), http.StatusBadRequest)
				return false
			}
			return true
		case <-r.Context().Done():
			return false
		case <-ctx.Done():
			http.Error(w, "Login cancelado ou expirado. Volte ao AnimeCaos.", http.StatusRequestTimeout)
			return false
		}
	}
	handler := http.NewServeMux()
	handler.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Referrer-Policy", "no-referrer")
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		if provider == "anilist" {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			io.WriteString(w, `<!doctype html><meta charset="utf-8"><title>AnimeCaos</title><p id="message">Conectando…</p><script>const p=new URLSearchParams(location.hash.slice(1));history.replaceState(null,'','/');fetch('/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:p.toString()}).then(r=>{document.getElementById('message').textContent=r.ok?'Conectado! Você pode voltar ao AnimeCaos.':'Login inválido. Volte ao aplicativo e tente novamente.'})</script>`)
			return
		}
		if subtle.ConstantTimeCompare([]byte(r.URL.Query().Get("state")), []byte(state)) != 1 {
			http.Error(w, "retorno de login inválido", 400)
			return
		}
		code := r.URL.Query().Get("code")
		if code == "" {
			http.Error(w, "autorização não concedida", 400)
			return
		}
		select {
		case received <- code:
		default:
		}
		if complete(w, r) {
			io.WriteString(w, "Conectado. Volte ao AnimeCaos.")
		}
	})
	handler.HandleFunc("/token", func(w http.ResponseWriter, r *http.Request) {
		if provider != "anilist" || r.Method != "POST" {
			w.WriteHeader(405)
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, 16384)
		if r.ParseForm() != nil || subtle.ConstantTimeCompare([]byte(r.Form.Get("state")), []byte(state)) != 1 {
			http.Error(w, "estado inválido", 400)
			return
		}
		token := r.Form.Get("access_token")
		if token == "" {
			http.Error(w, "sem token", 400)
			return
		}
		select {
		case received <- token:
		default:
		}
		if complete(w, r) {
			w.WriteHeader(204)
		}
	})
	server := http.Server{Handler: handler, ReadHeaderTimeout: 5 * time.Second}
	defer func() {
		shutdown, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		server.Shutdown(shutdown)
	}()
	defer close(finished)
	go server.Serve(listener)
	u := "https://anilist.co/api/v2/oauth/authorize?" + url.Values{"client_id": {AniListClientID}, "response_type": {"token"}, "redirect_uri": {redirect}, "state": {state}}.Encode()
	if provider == "mal" {
		u = "https://myanimelist.net/v1/oauth2/authorize?" + url.Values{"client_id": {malID}, "response_type": {"code"}, "redirect_uri": {redirect}, "state": {state}, "code_challenge": {verifier}, "code_challenge_method": {"plain"}}.Encode()
	}
	if e = a.Open(u); e != nil {
		return e
	}
	var token Token
	select {
	case <-ctx.Done():
		return fmt.Errorf("login cancelado ou expirado")
	case value := <-received:
		if provider == "anilist" {
			token = Token{Access: value, Expires: time.Now().Add(365 * 24 * time.Hour).Unix()}
		} else {
			token, e = a.exchange(ctx, url.Values{"client_id": {malID}, "grant_type": {"authorization_code"}, "code": {value}, "code_verifier": {verifier}, "redirect_uri": {redirect}})
			if e != nil {
				return e
			}
		}
	}
	if e = a.writeCredential("oauth:"+provider, provider, token); e != nil {
		return e
	}
	_, e = a.Profile(ctx, provider, malID)
	return e
}

func (a *Accounts) loginDiscord(parent context.Context) error {
	listener, err := net.Listen("tcp4", a.discordListenAddr())
	if err != nil {
		return fmt.Errorf("não foi possível iniciar retorno do login Discord: %w", err)
	}
	ctx, cancel := context.WithTimeout(parent, 2*time.Minute)
	defer cancel()
	state := random()
	verifier := random()
	received := make(chan string, 1)
	rejected := make(chan error, 1)
	finished := make(chan struct{})
	handler := http.NewServeMux()
	handler.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		if r.Method != http.MethodGet || r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		if subtle.ConstantTimeCompare([]byte(r.URL.Query().Get("state")), []byte(state)) != 1 {
			http.Error(w, "retorno de login inválido", http.StatusBadRequest)
			return
		}
		if issuer := r.URL.Query().Get("iss"); issuer != "https://discord.com" {
			http.Error(w, "servidor de autorização inválido", http.StatusBadRequest)
			return
		}
		if authError := r.URL.Query().Get("error"); authError != "" {
			message := "autorização Discord não concedida"
			if authError == "access_denied" {
				message = "login Discord cancelado pelo usuário"
			}
			select {
			case rejected <- errors.New(message):
			default:
			}
			http.Error(w, "Autorização do Discord não concluída. Volte ao AnimeCaos.", http.StatusBadRequest)
			return
		}
		code := r.URL.Query().Get("code")
		if code == "" {
			http.Error(w, "autorização não concedida", http.StatusBadRequest)
			return
		}
		select {
		case received <- code:
		default:
		}
		select {
		case <-finished:
			io.WriteString(w, "Conta conectada. Volte ao AnimeCaos.")
		case <-ctx.Done():
			http.Error(w, "Login cancelado ou expirado. Volte ao AnimeCaos.", http.StatusRequestTimeout)
		case <-r.Context().Done():
		}
	})
	server := http.Server{Handler: handler, ReadHeaderTimeout: 5 * time.Second}
	defer func() {
		shutdown, stop := context.WithTimeout(context.Background(), 2*time.Second)
		defer stop()
		_ = server.Shutdown(shutdown)
	}()
	defer close(finished)
	go func() {
		_ = server.Serve(listener)
	}()
	redirect := a.discordRedirectURI()
	authorizeURL, err := url.Parse(a.discordAuthorizeURL())
	if err != nil {
		return fmt.Errorf("URL de autorização Discord inválida: %w", err)
	}
	query := authorizeURL.Query()
	query.Set("client_id", DiscordClientID)
	query.Set("response_type", "code")
	query.Set("scope", "identify")
	query.Set("redirect_uri", redirect)
	query.Set("state", state)
	query.Set("code_challenge", pkceChallenge(verifier))
	query.Set("code_challenge_method", "S256")
	authorizeURL.RawQuery = query.Encode()
	if a.Open == nil {
		return fmt.Errorf("não foi possível abrir o navegador do sistema")
	}
	if err = a.Open(authorizeURL.String()); err != nil {
		return err
	}
	var token Token
	select {
	case <-ctx.Done():
		return fmt.Errorf("login Discord cancelado ou expirado")
	case err := <-rejected:
		return err
	case code := <-received:
		token, err = a.exchangeDiscord(ctx, url.Values{
			"client_id":     {DiscordClientID},
			"grant_type":    {"authorization_code"},
			"code":          {code},
			"code_verifier": {verifier},
			"redirect_uri":  {redirect},
		})
		if err != nil {
			return fmt.Errorf("Discord: troca de token: %w", err)
		}
	}
	if err = a.writeCredential("oauth:discord", "discord", token); err != nil {
		return err
	}
	_, err = a.Profile(ctx, "discord", "")
	return err
}

func (a *Accounts) exchangeDiscord(ctx context.Context, form url.Values) (Token, error) {
	resp, err := a.Client.Do(ctx, http.MethodPost, a.discordOAuthBase()+"/token", []byte(form.Encode()), map[string]string{"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
	if err != nil {
		return Token{}, err
	}
	defer resp.Body.Close()
	var payload struct {
		Access  string `json:"access_token"`
		Refresh string `json:"refresh_token"`
		Expires int64  `json:"expires_in"`
	}
	if err = json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&payload); err != nil {
		return Token{}, fmt.Errorf("resposta de token inválida: %w", err)
	}
	if payload.Access == "" {
		return Token{}, fmt.Errorf("Discord não retornou token de acesso")
	}
	return Token{Access: payload.Access, Refresh: payload.Refresh, Expires: time.Now().Unix() + payload.Expires}, nil
}
func (a *Accounts) exchange(ctx context.Context, form url.Values) (Token, error) {
	clientID := form.Get("client_id")
	if clientID == "" {
		return Token{}, fmt.Errorf("configure o Client ID do MyAnimeList")
	}
	secret, err := a.malClientSecret()
	if err != nil {
		return Token{}, err
	}
	basic := base64.StdEncoding.EncodeToString([]byte(clientID + ":" + secret))
	r, e := a.Client.Do(ctx, "POST", a.malOAuthBase()+"/token", []byte(form.Encode()), map[string]string{"Authorization": "Basic " + basic, "Content-Type": "application/x-www-form-urlencoded"})
	if e != nil {
		return Token{}, fmt.Errorf("MyAnimeList: troca de token: %w", e)
	}
	defer r.Body.Close()
	var t struct {
		Access  string `json:"access_token"`
		Refresh string `json:"refresh_token"`
		Expires int64  `json:"expires_in"`
	}
	if e = json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&t); e != nil {
		return Token{}, e
	}
	if t.Access == "" {
		return Token{}, fmt.Errorf("MyAnimeList não retornou token")
	}
	return Token{Access: t.Access, Refresh: t.Refresh, Expires: time.Now().Unix() + t.Expires}, nil
}
func (a *Accounts) token(ctx context.Context, p, id string) (Token, error) {
	a.refresh.Lock()
	defer a.refresh.Unlock()
	var t Token
	if err := a.readCredential("oauth:"+p, p, &t); err != nil {
		if securestore.IsNotFound(err) || errors.Is(err, sql.ErrNoRows) {
			return t, fmt.Errorf("conta não conectada")
		}
		return t, fmt.Errorf("credencial da conta indisponível: %w", err)
	}
	if t.Access == "" {
		return t, fmt.Errorf("conta não conectada")
	}
	if (p == "mal" || p == "discord") && t.Refresh != "" && time.Now().Unix() >= t.Expires-120 {
		form := url.Values{"client_id": {id}, "grant_type": {"refresh_token"}, "refresh_token": {t.Refresh}}
		var n Token
		var e error
		if p == "discord" {
			form.Set("client_id", DiscordClientID)
			n, e = a.exchangeDiscord(ctx, form)
		} else {
			n, e = a.exchange(ctx, form)
		}
		if e != nil {
			return t, e
		}
		if n.Refresh == "" {
			n.Refresh = t.Refresh
		}
		t = n
		if err := a.writeCredential("oauth:"+p, p, t); err != nil {
			return t, err
		}
	}
	return t, nil
}
func (a *Accounts) Logout(p string) error {
	profileErr := a.Store.Delete("accounts", p)
	credentialErr := a.deleteCredential("oauth:"+p, p)
	return errors.Join(profileErr, credentialErr)
}
func (a *Accounts) Profiles() []Account {
	out := []Account{}
	for _, p := range []string{"anilist", "mal", "discord"} {
		var v Account
		a.Store.Get("accounts", p, &v)
		v.Provider = p
		var t Token
		if err := a.readCredential("oauth:"+p, p, &t); err == nil {
			v.Connected = t.Access != ""
		} else if !securestore.IsNotFound(err) && !errors.Is(err, sql.ErrNoRows) {
			v.Error = fmt.Sprintf("Não foi possível acessar a credencial protegida: %v", err)
		}
		out = append(out, v)
	}
	return out
}
func (a *Accounts) Profile(ctx context.Context, p, id string) (Account, error) {
	if p != "anilist" && p != "mal" && p != "discord" {
		return Account{Provider: p}, fmt.Errorf("integração desconhecida")
	}
	out := Account{Provider: p}
	t, e := a.token(ctx, p, id)
	if e != nil {
		return out, e
	}
	out.Connected = true
	if p == "anilist" {
		var r struct {
			Viewer struct {
				ID     int    `json:"id"`
				Name   string `json:"name"`
				Avatar struct {
					Large string `json:"large"`
				} `json:"avatar"`
				Statistics struct {
					Anime struct {
						Count    int `json:"count"`
						Episodes int `json:"episodesWatched"`
						Minutes  int `json:"minutesWatched"`
					} `json:"anime"`
				} `json:"statistics"`
			} `json:"Viewer"`
		}
		e = a.Meta.Query(ctx, `query {Viewer {id name avatar {large} statistics {anime {count episodesWatched minutesWatched}}}}`, nil, t.Access, &r)
		out.ID = r.Viewer.ID
		out.Name = r.Viewer.Name
		out.Avatar = r.Viewer.Avatar.Large
		out.AnimeCount = r.Viewer.Statistics.Anime.Count
		out.Episodes = r.Viewer.Statistics.Anime.Episodes
		out.Minutes = r.Viewer.Statistics.Anime.Minutes
	} else if p == "mal" {
		if e = a.MALGate.Wait(ctx); e != nil {
			return out, e
		}
		var r struct {
			ID      int    `json:"id"`
			Name    string `json:"name"`
			Picture string `json:"picture"`
			Stats   struct {
				Count    int     `json:"num_items"`
				Episodes int     `json:"num_episodes"`
				Days     float64 `json:"num_days_watched"`
			} `json:"anime_statistics"`
		}
		e = a.Client.JSON(ctx, "GET", a.malAPIBase()+"/users/@me?fields=anime_statistics,picture", nil, map[string]string{"Authorization": "Bearer " + t.Access, "X-MAL-CLIENT-ID": id}, &r)
		out.ID = r.ID
		out.Name = r.Name
		out.Avatar = r.Picture
		out.AnimeCount = r.Stats.Count
		out.Episodes = r.Stats.Episodes
		out.Minutes = int(r.Stats.Days * 1440)
	} else {
		var r struct {
			ID            string `json:"id"`
			Username      string `json:"username"`
			GlobalName    string `json:"global_name"`
			Discriminator string `json:"discriminator"`
			Avatar        string `json:"avatar"`
		}
		e = a.Client.JSON(ctx, http.MethodGet, a.discordAPIBase()+"/users/@me", nil, map[string]string{"Authorization": "Bearer " + t.Access}, &r)
		out.ExternalID = r.ID
		out.Name = r.GlobalName
		if out.Name == "" {
			out.Name = r.Username
			if r.Discriminator != "" && r.Discriminator != "0" {
				out.Name += "#" + r.Discriminator
			}
		}
		if r.Avatar != "" && r.ID != "" {
			extension := "png"
			if strings.HasPrefix(r.Avatar, "a_") {
				extension = "gif"
			}
			out.Avatar = fmt.Sprintf("https://cdn.discordapp.com/avatars/%s/%s.%s?size=128", url.PathEscape(r.ID), url.PathEscape(r.Avatar), extension)
		} else if r.ID != "" {
			if snowflake, parseErr := strconv.ParseUint(r.ID, 10, 64); parseErr == nil {
				out.Avatar = fmt.Sprintf("https://cdn.discordapp.com/embed/avatars/%d.png", (snowflake>>22)%6)
			}
		}
	}
	if e != nil {
		return out, e
	}
	var cached Account
	if p != "discord" && a.Store.Get("accounts", p, &cached) == nil && out.AnimeCount == 0 && out.Episodes == 0 && cached.AnimeCount > 0 {
		out.AnimeCount = cached.AnimeCount
		out.Episodes = cached.Episodes
		out.Minutes = cached.Minutes
	}
	return out, a.Store.Put("accounts", p, out)
}
func (a *Accounts) Sync(ctx context.Context, p, clientID string, mediaID, episode, total int) error {
	if p != "anilist" && p != "mal" {
		return fmt.Errorf("integração desconhecida")
	}
	if mediaID <= 0 {
		return fmt.Errorf("anime sem correspondência no tracker")
	}
	if episode <= 0 {
		return fmt.Errorf("número de episódio inválido para sincronização")
	}
	// A read-before-write prevents an older/replayed episode from moving a
	// user's remote list backwards. Serialize updates so concurrent player
	// events cannot race between that read and the mutation.
	a.syncMu.Lock()
	defer a.syncMu.Unlock()
	t, e := a.token(ctx, p, clientID)
	if e != nil {
		return e
	}
	status := "CURRENT"
	if total > 0 && episode >= total {
		status = "COMPLETED"
	}
	if p == "anilist" {
		var current struct {
			Media struct {
				Entry *struct {
					Progress int    `json:"progress"`
					Status   string `json:"status"`
				} `json:"mediaListEntry"`
			} `json:"Media"`
		}
		if e := a.Meta.Query(ctx, `query($id:Int){Media(id:$id){mediaListEntry{progress status}}}`, map[string]any{"id": mediaID}, t.Access, &current); e != nil {
			return fmt.Errorf("AniList: leitura do progresso atual: %w", e)
		}
		if entry := current.Media.Entry; entry != nil {
			if entry.Status == "COMPLETED" || entry.Progress > episode || (entry.Progress == episode && entry.Status == status) {
				return nil
			}
		}
		var result any
		return a.Meta.Query(ctx, `mutation($id:Int,$ep:Int,$status:MediaListStatus){SaveMediaListEntry(mediaId:$id,progress:$ep,status:$status){id progress}}`, map[string]any{"id": mediaID, "ep": episode, "status": status}, t.Access, &result)
	}
	if status == "CURRENT" {
		status = "watching"
	} else {
		status = "completed"
	}
	if e = a.MALGate.Wait(ctx); e != nil {
		return e
	}
	var current struct {
		ListStatus *struct {
			Status   string `json:"status"`
			Episodes int    `json:"num_episodes_watched"`
		} `json:"my_list_status"`
	}
	if e = a.Client.JSON(ctx, "GET", fmt.Sprintf("%s/anime/%d?fields=my_list_status", a.malAPIBase(), mediaID), nil, map[string]string{"Authorization": "Bearer " + t.Access, "X-MAL-CLIENT-ID": clientID}, &current); e != nil {
		return fmt.Errorf("MyAnimeList: leitura do progresso atual: %w", e)
	}
	if entry := current.ListStatus; entry != nil {
		if entry.Status == "completed" || entry.Episodes > episode || (entry.Episodes == episode && entry.Status == status) {
			return nil
		}
	}
	if e = a.MALGate.Wait(ctx); e != nil {
		return e
	}
	r, e := a.Client.Do(ctx, "PATCH", fmt.Sprintf("%s/anime/%d/my_list_status", a.malAPIBase(), mediaID), []byte(url.Values{"status": {strings.ToLower(status)}, "num_watched_episodes": {fmt.Sprint(episode)}}.Encode()), map[string]string{"Authorization": "Bearer " + t.Access, "X-MAL-CLIENT-ID": clientID, "Content-Type": "application/x-www-form-urlencoded"})
	if r != nil {
		r.Body.Close()
	}
	return e
}
