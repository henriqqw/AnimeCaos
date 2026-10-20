import Image from "./Image";
import { createPortal } from "react-dom";
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { api, desktop, on, op } from "./api";
import {
  key,
  type Anime,
  type Detail,
  type History,
  type Settings,
  type Download,
  type LocalFile,
  type Account,
  type Manga,
  type MangaCategory,
  type Chapter,
  type MangaDiscovery,
  type MangaProgress,
  type PlayerEvent,
  type Update,
} from "./types";

type Route = {
  name: string;
  query?: string;
  anime?: Anime;
  manga?: Manga;
  chapter?: Chapter;
  chapters?: Chapter[];
  pages?: string[];
  page?: number;
};
const names: Record<string, string> = {
  home: "Início",
  search: "Pesquisar",
  list: "Minha Lista",
  history: "Histórico",
  downloads: "Downloads",
  manga: "Mangás",
  accounts: "Contas",
  settings: "Configurações",
  logs: "Diagnóstico",
};
const time = (n: number) =>
  `${Math.floor(n / 60)}:${String(Math.floor(n % 60)).padStart(2, "0")}`;
const HISTORY_PAGE_SIZE = 24;
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
const userMessage = (value: string) =>
  value
    .replace(/https?:\/\/[^\s)]+/gi, "serviço externo")
    .replace(/animefire|animesonlinecc|betteranime/gi, "fonte de conteúdo");

const navPaths: Record<string, string> = {
  home: "M3 10.5 12 3l9 7.5M5.5 9v11h13V9M9 20v-6h6v6",
  search: "m20 20-4.2-4.2M18 10.5a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0Z",
  list: "M6 4h12v17l-6-4-6 4V4ZM9 8h6M9 11h6",
  play: "m8 5 11 7-11 7V5Z",
  trash: "M4 7h16M10 11v6m4-6v6M5.5 7l1 13h11l1-13M9 7V4h6v3",
  folder: "M3 7.5A2.5 2.5 0 0 1 5.5 5H10l2 2h6.5A2.5 2.5 0 0 1 21 9.5v1M3.5 10.5h17l-2 8.5h-15l-1-8.5Z",
  folderOpen: "M3 7.5A2.5 2.5 0 0 1 5.5 5H10l2 2h6.5A2.5 2.5 0 0 1 21 9.5v1M3 12l2-2h16l-2 9H5l-2-7Z",
  refresh: "M20 7v5h-5M4 17v-5h5m10.5-5A7 7 0 0 0 7.4 5.3L5 8m14 8-2.4 2.7A7 7 0 0 1 6.5 16.7",
  history: "M3 12a9 9 0 1 0 2.6-6.4L3 8m0-5v5h5m4-1v5l3 2",
  downloads: "M12 3v12m-5-5 5 5 5-5M4 19v2h16v-2",
  manga: "M4 4.5A2.5 2.5 0 0 1 6.5 2H20v18H6.5A2.5 2.5 0 0 1 4 17.5v-13ZM4 16h16M8 6h8m-8 3h8",
  settings: "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7ZM19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.7 2.9-.2-.1a1.7 1.7 0 0 0-1.9.2l-.2.1h-3.4l-.1-.2a1.7 1.7 0 0 0-1.7-1l-.2.1-2.9-1.7.1-.2a1.7 1.7 0 0 0-.2-1.9l-.1-.2v-3.4l.2-.1a1.7 1.7 0 0 0 1-1.7l-.1-.2 1.7-2.9.2.1a1.7 1.7 0 0 0 1.9-.2l.2-.1h3.4l.1.2a1.7 1.7 0 0 0 1.7 1l.2-.1 2.9 1.7-.1.2a1.7 1.7 0 0 0 .2 1.9l.1.2v3.4l-.2.1",
  arrow: "M5 12h14m-7-7 7 7-7 7",
};
function NavIcon({ name }: { name: string }) {
  return <svg className="nav-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d={navPaths[name] || navPaths.home} /></svg>;
}
function SidebarToggle({ collapsed, mobile = false, onClick }: { collapsed: boolean; mobile?: boolean; onClick: () => void }) {
  const label = collapsed ? "Expandir menu" : "Recolher menu";
  return (
    <button
      className={mobile ? "sidebar-toggle mobile-sidebar-toggle" : "sidebar-toggle"}
      aria-label={label}
      aria-expanded={!collapsed}
      title={label}
      onClick={onClick}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3.5" y="4" width="17" height="16" rx="2" />
        <path d={collapsed ? "m13 9 3 3-3 3M8 4v16" : "m11 9-3 3 3 3M8 4v16"} />
      </svg>
    </button>
  );
}

export default function App() {
  const [route, setRoute] = useState<Route>({ name: "home" }),
    [trail, setTrail] = useState<Route[]>([]),
    [settings, setSettings] = useState<Settings>(),
    [headerQuery, setHeaderQuery] = useState(""),
    [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("animecaos-sidebar-collapsed") === "true"),
    [version, setVersion] = useState("3.0.0-dev"),
    [error, setError] = useState(""),
    [logs, setLogs] = useState<string[]>([]),
    [library, setLibrary] = useState<Anime[]>([]),
    [player, setPlayer] = useState<PlayerEvent>(),
    [queue, setQueue] = useState<Download[]>([]),
    [queueLoaded, setQueueLoaded] = useState(false),
    [panel, setPanel] = useState(false);
  const [settingsSaveState, setSettingsSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const settingsRef = useRef<Settings | null>(null);
  const pendingSettingsRef = useRef<Settings | null>(null);
  const settingsSaveTimer = useRef<number | null>(null);
  const settingsSaveRunning = useRef(false);
  const report = (e: unknown) => {
    const m = message(e);
    if (/context canceled|operation was canceled/i.test(m)) return;
    setError(userMessage(m));
    setLogs((v) =>
      [`${new Date().toLocaleTimeString()} ${m}`, ...v].slice(0, 200),
    );
  };
  const toggleSidebar = () => setSidebarCollapsed((current) => {
    const next = !current;
    localStorage.setItem("animecaos-sidebar-collapsed", String(next));
    return next;
  });
  const run = async <T,>(f: () => Promise<T>) => {
    try {
      return await f();
    } catch (e) {
      report(e);
    }
  };
  const flushSettingsSave = async () => {
    if (settingsSaveRunning.current) return;
    settingsSaveRunning.current = true;
    let failed = false;
    try {
      while (pendingSettingsRef.current) {
        const snapshot = pendingSettingsRef.current;
        pendingSettingsRef.current = null;
        setSettingsSaveState("saving");
        try {
          await api.SaveSettings(snapshot);
          localStorage.setItem("animecaos-theme", snapshot.theme || "system");
          if (pendingSettingsRef.current) continue;
          setSettingsSaveState("saved");
        } catch {
          if (!pendingSettingsRef.current) pendingSettingsRef.current = snapshot;
          setSettingsSaveState("error");
          failed = true;
          break;
        }
      }
    } finally {
      settingsSaveRunning.current = false;
      if (pendingSettingsRef.current && !failed) {
        settingsSaveTimer.current = window.setTimeout(() => void flushSettingsSave(), 0);
      }
    }
  };
  const updateSettings = (patch: Partial<Settings>, immediate = false) => {
    const current = settingsRef.current;
    if (!current) return;
    const next = { ...current, ...patch };
    settingsRef.current = next;
    pendingSettingsRef.current = next;
    setSettings(next);
    setSettingsSaveState("saving");
    if (settingsSaveTimer.current) window.clearTimeout(settingsSaveTimer.current);
    settingsSaveTimer.current = window.setTimeout(() => void flushSettingsSave(), immediate ? 0 : 350);
  };
  const retrySettingsSave = () => {
    if (!pendingSettingsRef.current && settingsRef.current) pendingSettingsRef.current = settingsRef.current;
    setSettingsSaveState("saving");
    if (settingsSaveTimer.current) window.clearTimeout(settingsSaveTimer.current);
    settingsSaveTimer.current = window.setTimeout(() => void flushSettingsSave(), 0);
  };
  const navigate = (next: Route) => {
    setTrail((v) => [...v, route]);
    setRoute(next);
    setError("");
  };
  const back = () =>
    setTrail((v) => {
      if (v.length) setRoute(v[v.length - 1]);
      return v.slice(0, -1);
    });
  const isMangaRoute = route.name === "manga" || route.name === "chapters" || route.name === "reader";
  const focusHomeSearch = () => {
    if (!isMangaRoute && route.name !== "home") navigate({ name: "home" });
    window.setTimeout(() => {
      const input = document.querySelector<HTMLInputElement>(".header-search input");
      input?.focus();
      input?.select();
    }, 0);
  };
  useEffect(() => {
    setHeaderQuery(route.name === "search" || route.name === "manga" ? route.query || route.anime?.title || "" : "");
  }, [route.name, route.query, route.anime?.id]);
  const refreshLibrary = () => api.Library().then(setLibrary).catch(report);
  const favorite = async (a: Anime) => {
    const enabled = !library.some((v) => key(v) === key(a));
    await api.Favorite(a, enabled);
    setLibrary((items) =>
      enabled
        ? items.some((v) => key(v) === key(a))
          ? items
          : [...items, a]
        : items.filter((v) => key(v) !== key(a)),
    );
  };
  useEffect(() => {
    api
      .Initial()
      .then((v) => {
        settingsRef.current = v.settings;
        setSettings(v.settings);
        setVersion(v.version);
      })
      .catch(report);
    refreshLibrary();
    api.Downloads().then((items) => { setQueue(items); setQueueLoaded(true); }).catch((e) => { report(e); setQueueLoaded(true); });
    const off = [
      on<PlayerEvent | null>("player", (e) => {
        setPlayer(e || undefined);
        if (e?.state.error) report(e.state.error);
      }),
      on<string>("error", report),
      on<Download>("download", (d) => {
        setQueueLoaded(true);
        setQueue((v) => {
          const i = v.findIndex((x) => x.id === d.id);
          if (i < 0) return [...v, d];
          return v.map((x) => (x.id === d.id ? d : x));
        });
      }),
    ];
    return () => off.forEach((f) => f());
  }, []);
  useEffect(() => () => {
    if (settingsSaveTimer.current) window.clearTimeout(settingsSaveTimer.current);
  }, []);
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if (e.ctrlKey && (e.key === "f" || e.key === "k")) {
        e.preventDefault();
        focusHomeSearch();
      }
      if (e.altKey && e.key === "ArrowLeft") {
        e.preventDefault();
        back();
      }
      if (e.ctrlKey && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
        e.preventDefault();
        run(() => api.Adjacent(e.key === "ArrowRight" ? 1 : -1));
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, [route, trail]);
  useEffect(() => {
    if (
      !settings?.autoClose ||
      !panel ||
      queue.some((x) =>
        ["queued", "resolving", "downloading"].includes(x.status),
      )
    )
      return;
    const t = setTimeout(() => setPanel(false), settings.autoCloseMs);
    return () => clearTimeout(t);
  }, [queue, panel, settings?.autoClose, settings?.autoCloseMs]);
  const enqueue = async (d: Detail, ids: Set<string>) => {
    await api.Enqueue(
      d.anime,
      d.episodes.filter((e) => ids.has(e.id)),
    );
    setPanel(true);
  };
  if (!settings)
    return (
      <main className="boot" data-theme={localStorage.getItem("animecaos-theme") || "system"} aria-busy="true">
        <img src="/animecaos-wordmark.png" alt="AnimeCaos" className="boot-logo" />
        <small>v{version}</small>
        <p>{error || "Abrindo sua biblioteca…"}</p>
      </main>
    );
  return (
    <div
      className={`app${sidebarCollapsed ? " sidebar-collapsed" : ""}`}
      data-theme={settings.theme || "system"}
      style={{ fontSize: `${settings.uiScale}rem` }}
      onMouseUp={(e) => {
        if (e.button === 3) back();
      }}
    >
      <aside>
        <div className="brand">
          <img src="/animecaos-wordmark.png" alt="AnimeCaos" className="brand-wordmark" />
          <img src="/animecaos-icon.png" alt="" className="brand-icon" />
          <SidebarToggle collapsed={sidebarCollapsed} onClick={toggleSidebar} />
        </div>
        <small>v{version}</small>
        <nav aria-label="Navegação principal">
          {Object.entries(names).filter(([id]) => id !== "accounts" && id !== "logs").map(([id, label]) => (
            <button
              key={id}
              className={route.name === id ? "active" : ""}
              title={sidebarCollapsed ? label : undefined}
              onClick={() => id === "search" ? focusHomeSearch() : navigate({ name: id })}
            >
              <NavIcon name={id} />
              <span className="nav-label">{label}</span>
            </button>
          ))}
        </nav>
      </aside>
      <main>
        <header>
          <SidebarToggle collapsed={sidebarCollapsed} mobile onClick={toggleSidebar} />
          <button className="header-back" aria-label="Voltar" disabled={!trail.length} onClick={back}>
            <span aria-hidden="true">←</span><span className="header-back-label">Voltar</span>
          </button>
          <h2 className="header-title">
            {names[route.name] ||
              route.anime?.title ||
              route.manga?.title ||
              "Leitor"}
          </h2>
          <form className="header-search" role="search" onSubmit={(e) => {
            e.preventDefault();
            const query = headerQuery.trim();
            if (!query) return;
            if (isMangaRoute) {
              if (route.name === "manga") setRoute({ name: "manga", query });
              else navigate({ name: "manga", query });
              setError("");
              return;
            }
            if (route.name === "search") {
              setRoute({ name: "search", query });
              setError("");
            } else navigate({ name: "search", query });
          }}>
            <NavIcon name="search" />
            <input type="search" aria-label={isMangaRoute ? "Buscar mangás" : "Buscar animes"} placeholder={isMangaRoute ? "Buscar mangás..." : "Buscar animes..."} value={headerQuery} onChange={(e) => setHeaderQuery(e.target.value)} />
            <kbd>Ctrl K</kbd>
          </form>
          <button
            className="download-toggle"
            aria-label={`Downloads${queue.filter((x) => ["queued", "resolving", "downloading"].includes(x.status)).length ? `, ${queue.filter((x) => ["queued", "resolving", "downloading"].includes(x.status)).length} ativos` : ""}`}
            title="Downloads"
            aria-expanded={panel}
            onClick={() => setPanel((v) => !v)}
          >
            <NavIcon name="downloads" />
            {queue.some((x) => ["queued", "resolving", "downloading"].includes(x.status)) && <span className="download-badge">{queue.filter((x) => ["queued", "resolving", "downloading"].includes(x.status)).length}</span>}
          </button>
        </header>
        {error && (
          <div role="alert" className="alert">
            <span>{error}</span>
            <button aria-label="Fechar erro" onClick={() => setError("")}>
              ×
            </button>
          </div>
        )}
        <section
          className="content"
          key={
            route.name +
            (route.anime?.id || route.manga?.id || route.chapter?.id || route.query || "")
          }
        >
          {route.name === "home" && (
            <Home
              open={(a) => navigate({ name: "search", anime: a })}
              openHistory={(a) => navigate({ name: "detail", anime: a })}
              report={report}
            />
          )}
          {route.name === "search" && (
            <Search
              open={(a) => navigate({ name: "detail", anime: a })}
              preferred={route.anime}
              initialQuery={route.query}
              report={report}
            />
          )}
          {route.name === "list" && (
            <>
              <Cards
                items={library}
                open={(a) => navigate({ name: "detail", anime: a })}
              />
              {!library.length && (
                <Empty>
                  Adicione animes à Minha Lista na tela de detalhes.
                </Empty>
              )}
            </>
          )}
          {route.name === "detail" && route.anime && (
            <Details
              anime={route.anime}
              favorite={favorite}
              saved={library.some((a) => key(a) === key(route.anime!))}
              enqueue={enqueue}
              report={report}
              search={() => navigate({ name: "search" })}
            />
          )}
          {route.name === "history" && (
            <HistoryView
              open={(a) => navigate({ name: "detail", anime: a })}
              search={(a) => navigate({ name: "search", anime: a })}
              report={report}
            />
          )}
          {route.name === "downloads" && (
            <DownloadsView
              queue={queue}
              report={report}
              openAnime={(a) => navigate({ name: "detail", anime: a })}
              reader={(pages) => navigate({ name: "reader", pages })}
            />
          )}
          {route.name === "manga" && (
            <MangaView
              open={(m) => navigate({ name: "chapters", manga: m })}
              resume={(p) =>
                navigate({
                  name: "reader",
                  manga: p.manga,
                  chapter: p.chapter,
                  page: p.page,
                })
              }
              initialQuery={route.query}
              sharedQuery={headerQuery}
              syncQuery={setHeaderQuery}
              report={report}
            />
          )}
          {route.name === "chapters" && route.manga && (
            <ChaptersView
              manga={route.manga}
              open={(c, chapters) =>
                navigate({ name: "reader", manga: route.manga, chapter: c, chapters })
              }
              report={report}
              showQueue={() => setPanel(true)}
            />
          )}
          {route.name === "reader" && (
            <Reader
              route={route}
              report={report}
              back={back}
              changeChapter={(chapter, chapters) =>
                setRoute({ name: "reader", manga: route.manga, chapter, chapters })
              }
            />
          )}
          {route.name === "accounts" && <AccountsView />}
          {route.name === "settings" && (
            <SettingsView
              settings={settings}
              navigate={(name) => navigate({ name })}
              onChange={updateSettings}
              saveState={settingsSaveState}
              retrySave={retrySettingsSave}
              report={report}
            />
          )}
          {route.name === "logs" && <Diagnostics logs={logs} report={report} />}
        </section>
      </main>
      {panel && (
        <section className="queue" aria-label="Downloads" aria-busy={!queueLoaded}>
          <header className="queue-heading">
            <div><h3>Downloads</h3><small>{queue.filter((x) => ["queued", "resolving", "downloading"].includes(x.status)).length ? `${queue.filter((x) => ["queued", "resolving", "downloading"].includes(x.status)).length} em andamento` : "Sua atividade recente"}</small></div>
            <button className="queue-close" aria-label="Fechar downloads" title="Fechar" onClick={() => setPanel(false)}>×</button>
          </header>
          <Queue items={queue} loading={!queueLoaded} report={report} openAnime={(a) => { setPanel(false); navigate({ name: "detail", anime: a }); }} />
        </section>
      )}
      {player && (
        <footer className="player">
          <div>
            <strong>{player.anime.title}</strong>
            <small>
              Temporada {player.episode.season} · Episódio{" "}
              {player.episode.number}
            </small>
          </div>
          <button
            disabled={player.anime.provider === "local"}
            onClick={() => run(() => api.Adjacent(-1))}
            aria-label="Episódio anterior"
          >
            ⏮
          </button>
          <button disabled={!player.state.playing} onClick={() => run(() => api.PlayerCommand("pause", 0))}>
            {player.state.playing
              ? player.state.paused ? "Retomar" : "Pausar"
              : player.state.eof ? "Concluído" : "Encerrado"}
          </button>
          <button
            disabled={player.anime.provider === "local"}
            onClick={() => run(() => api.Adjacent(1))}
            aria-label="Próximo episódio"
          >
            ⏭
          </button>
          <span>{time(player.state.position)}</span>
          <input
            aria-label="Posição do vídeo"
            type="range"
            min="0"
            max={player.state.duration || 1}
            value={player.state.position}
            onChange={(e) =>
              run(() => api.PlayerCommand("seek", +e.target.value))
            }
          />
          <span>{time(player.state.duration)}</span>
          <label>
            Volume
            <input
              aria-label="Volume"
              type="range"
              min="0"
              max="100"
              defaultValue="100"
              onChange={(e) =>
                run(() => api.PlayerCommand("volume", +e.target.value))
              }
            />
          </label>
          <label>
            <input
              type="checkbox"
              checked={settings.autoplay}
              onChange={(e) => updateSettings({ autoplay: e.target.checked })}
            />{" "}
            Autoplay
          </label>
          <button onClick={() => run(() => api.PlayerCommand("stop", 0))}>
            Fechar vídeo
          </button>
        </footer>
      )}
    </div>
  );
}
function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty">
      {children}
      <p>
        <button
          onClick={() =>
            desktop().OpenLink("https://github.com/henriqqw/animecaos")
          }
        >
          Projeto e comunidade
        </button>
      </p>
    </div>
  );
}
function Busy({ cancel, message = "Carregando…" }: { cancel?: () => void; message?: string }) {
  return (
    <div role="status" className="loading" aria-label={message}>
      <span className="loading-label">{message.replace(/…+$/, "")}</span>
      <span className="loading-dots" aria-hidden="true">
        <span /><span /><span />
      </span>
      {cancel && <button onClick={cancel}>Cancelar</button>}
    </div>
  );
}
function Cards({ items, open, layout = "grid", label = "Animes", showAvailability = false, showOpenOverlay = false }: { items: Anime[]; open: (a: Anime) => void; layout?: "grid" | "rail"; label?: string; showAvailability?: boolean; showOpenOverlay?: boolean }) {
  const cards = items.map((a) => <Card key={key(a)} a={a} open={() => open(a)} showAvailability={showAvailability} showOpenOverlay={showOpenOverlay} />);
  if (layout === "rail") return <Rail label={label}>{cards}</Rail>;
  return (
    <div className="cards">
      {cards}
    </div>
  );
}
function Rail({ children, label }: { children: ReactNode; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ left: false, right: false });
  const sync = () => {
    const node = ref.current;
    if (!node) return;
    const next = { left: node.scrollLeft > 2, right: node.scrollLeft + node.clientWidth < node.scrollWidth - 2 };
    setEdges((current) => current.left === next.left && current.right === next.right ? current : next);
  };
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    sync();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", sync);
      return () => window.removeEventListener("resize", sync);
    }
    const observer = new ResizeObserver(sync);
    observer.observe(node);
    return () => observer.disconnect();
  }, [children]);
  const move = (direction: -1 | 1) => ref.current?.scrollBy({ left: direction * Math.max(260, ref.current.clientWidth * .8), behavior: "smooth" });
  return (
    <div className="carousel" role="region" aria-label={label}>
      {edges.left && <button className="carousel-arrow previous" aria-label={`Rolar ${label} para a esquerda`} onClick={() => move(-1)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6" /></svg></button>}
      <div className="cards rail" ref={ref} onScroll={sync}>{children}</div>
      {edges.right && <button className="carousel-arrow next" aria-label={`Rolar ${label} para a direita`} onClick={() => move(1)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg></button>}
    </div>
  );
}
function Card({ a, open, subtitle, action, onImageFailure, showAvailability = false, showOpenOverlay = false }: { a: Anime; open: () => void; subtitle?: string; action?: ReactNode; onImageFailure?: () => void; showAvailability?: boolean; showOpenOverlay?: boolean }) {
  const [preview, setPreview] = useState<Anime>();
  const [previewStyle, setPreviewStyle] = useState<CSSProperties>();
  const previewId = useId();
  const cardRef = useRef<HTMLElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null),
    closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null),
    request = useRef("");
  const leave = () => {
    if (timer.current) clearTimeout(timer.current);
    if (closeTimer.current) clearTimeout(closeTimer.current);
    if (request.current) api.Cancel(request.current);
    request.current = "";
    setPreview(undefined);
    setPreviewStyle(undefined);
  };
  const scheduleLeave = () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(leave, 180);
  };
  const keepPreviewOpen = () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
  };
  useEffect(() => leave, []);
  const positionPreview = () => {
    const card = cardRef.current;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    if (viewportWidth <= 760 || viewportHeight < 220) {
      setPreviewStyle(undefined);
      return;
    }
    const margin = 16;
    const gap = 12;
    const width = Math.min(280, viewportWidth - margin * 2);
    const maxHeight = Math.min(200, viewportHeight - margin * 2);
    const rightSpace = viewportWidth - rect.right - gap - margin;
    const leftSpace = rect.left - gap - margin;
    const placeRight = rightSpace >= width || rightSpace >= leftSpace;
    const sideSpace = placeRight ? rightSpace : leftSpace;
    const panelWidth = Math.min(width, Math.max(0, sideSpace));
    const left = placeRight ? rect.right + gap : rect.left - gap - panelWidth;
    const top = Math.max(
      margin,
      Math.min(rect.top + Math.min(24, rect.height * .12), viewportHeight - maxHeight - margin),
    );
    const theme = getComputedStyle(card.closest(".app") || card);
    setPreviewStyle({
      position: "fixed", left: Math.max(margin, Math.min(left, viewportWidth - panelWidth - margin)), top,
      width: panelWidth, maxHeight,
      "--surface-raised": theme.getPropertyValue("--surface-raised"),
      "--text": theme.getPropertyValue("--text"),
      "--border": theme.getPropertyValue("--border"),
      "--shadow": theme.getPropertyValue("--shadow"),
      "--accent": theme.getPropertyValue("--accent"),
      "--muted": theme.getPropertyValue("--muted"),
    } as CSSProperties);
  };
  useEffect(() => {
    if (!preview) return;
    let frame = 0;
    const reposition = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(positionPreview);
    };
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    const card = cardRef.current;
    const observer = typeof ResizeObserver === "undefined" || !card
      ? undefined
      : new ResizeObserver(reposition);
    if (card) observer?.observe(card);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
      observer?.disconnect();
    };
  }, [preview]);
  const schedulePreview = () => {
    if (window.innerWidth <= 760) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const id = op();
      request.current = id;
      api
        .Preview(id, a.title, a.anilistId || 0)
        .then((v) => {
          if (request.current === id) {
            positionPreview();
            setPreview(v);
          }
        })
        .catch(() => {});
    }, 450);
  };
  return (
    <>
    <article
      className="card"
      ref={cardRef}
      onMouseEnter={schedulePreview}
      onMouseLeave={scheduleLeave}
      onFocus={schedulePreview}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) scheduleLeave();
      }}
    >
      <button onClick={open} aria-describedby={preview ? previewId : undefined}>
        <span className="card-poster">
          {a.cover ? (
            <Image src={a.cover} loading="lazy" alt="" onLoadFailure={onImageFailure} />
          ) : (
            <span className="cover-placeholder">AC</span>
          )}
          {showAvailability && a.availability && <span className="quality-badge" title={`${a.availability.sourcesVerified.length} fonte(s) validada(s) · ${a.availability.sampleEpisode}`}>
            {a.availability.quality || "Qualidade não identificada"}
          </span>}
          {showOpenOverlay && <>
            <span className="card-open-overlay" aria-hidden="true" />
            <span className="card-open-cta" aria-hidden="true">Ver anime <NavIcon name="arrow" /></span>
          </>}
        </span>
        <strong className="card-title" title={a.title}>{a.title}</strong>
        {showAvailability && (a.year > 0 || a.episodeCount > 0 || a.format === "MOVIE") && <small className="card-meta">{[
          a.year > 0 ? a.year : "",
          a.format === "MOVIE" ? "Filme" : a.episodeCount > 0 ? `${a.episodeCount} eps.` : "",
        ].filter(Boolean).join(" · ")}</small>}
        {subtitle && <small className="card-subtitle">{subtitle}</small>}
      </button>
      {action && <div className="card-actions">{action}</div>}
    </article>
      {preview && previewStyle && createPortal(
        <div className="preview" id={previewId} role="tooltip" style={previewStyle} onMouseEnter={keepPreviewOpen} onMouseLeave={scheduleLeave}>
          <strong className="preview-title">{preview.title}</strong>
          <p className="preview-meta">
            <span className="rating-star" aria-hidden="true">★</span> {preview.score || "—"} · {preview.episodeCount || "?"} episódios
          </p>
          {preview.description && <p className="preview-description">{preview.description.replace(/<[^>]*>/g, "")}</p>}
        </div>,
        document.body,
      )}
    </>
  );
}
function Home({
  open,
  openHistory,
  report,
}: {
  open: (a: Anime) => void;
  openHistory: (a: Anime) => void;
  report: (e: unknown) => void;
}) {
  const [data, setData] = useState<{
      trending: Anime[];
      seasonal: Anime[];
      warning: string;
    }>(),
    [spot, setSpot] = useState(0),
    [coverFallback, setCoverFallback] = useState(false),
    [heroImageFailed, setHeroImageFailed] = useState(false);
  useEffect(() => {
    const id = op();
    api.Discover(id).then(setData).catch(report);
    return () => {
      api.Cancel(id);
    };
  }, []);
  useEffect(() => {
    const count = Math.max(1, Math.min(5, data?.trending.length || 1));
    const t = setInterval(() => setSpot((v) => (v + 1) % count), 7000);
    return () => clearInterval(t);
  }, [data?.trending.length]);
  useEffect(() => {
    setCoverFallback(false);
    setHeroImageFailed(false);
  }, [data?.trending[spot]?.id]);
  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable=true]")) return;
      const rail = target?.closest<HTMLElement>(".cards.rail");
      if (rail) {
        event.preventDefault();
        rail.scrollBy({ left: (event.key === "ArrowRight" ? 1 : -1) * Math.max(240, rail.clientWidth * .75), behavior: "smooth" });
        return;
      }
      if (target?.closest(".spotlight") || target === document.body) {
        event.preventDefault();
        const count = Math.min(5, data?.trending.length || 0);
        if (count) setSpot((value) => (value + (event.key === "ArrowRight" ? 1 : -1) + count) % count);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [data?.trending.length]);
  if (!data) return <section aria-label="Carregando destaques" className="skeleton-grid">{Array.from({ length: 6 }, (_, i) => <div className="skeleton-card" key={i}><div className="skeleton poster-skeleton" /><div className="skeleton line-skeleton" /><div className="skeleton short-skeleton" /></div>)}</section>;
  const featured = data.trending.slice(0, 5);
  const a = featured[spot % Math.max(1, featured.length)];
  return (
    <>
      {data.warning && <p role="status">{data.warning}</p>}
      {a && (
        <section
          className="spotlight"
        >
          {(a.banner || a.cover) && !heroImageFailed && <Image className="spotlight-image" src={coverFallback ? a.cover : a.banner || a.cover} alt="" onLoadFailure={() => {
            if (!coverFallback && a.banner && a.cover) setCoverFallback(true);
            else setHeroImageFailed(true);
          }} />}
          <div className="spotlight-shade" aria-hidden="true" />
          <div className="spotlight-copy">
            <span className="spotlight-eyebrow">DESTAQUE</span>
            <h2 title={a.title}>{a.title}</h2>
            <p>{a.description?.replace(/<[^>]*>/g, "").slice(0, 240)}</p>
            <button className="spotlight-action" onClick={() => open(a)}><svg className="play-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5 11 7-11 7V5Z" /></svg>Assistir</button>
          </div>
          <div className="spotlight-dots" role="group" aria-label="Selecionar destaque">
            {featured.map((x, i) => (
              <button
                key={x.id}
                aria-label={`Destaque ${i + 1}: ${x.title}`}
                aria-pressed={i === spot}
                onClick={() => setSpot(i)}
              ><span /></button>
            ))}
          </div>
        </section>
      )}
      <HistoryView limit={8} variant="shelf" open={openHistory} report={report} showOpenOverlay />
      <section className="home-shelf">
        <div className="shelf-heading"><h3>Em alta</h3></div>
        <Cards items={data.trending} open={open} layout="rail" label="Em alta" showOpenOverlay />
      </section>
      <section className="home-shelf">
        <div className="shelf-heading"><h3>Temporada atual</h3></div>
        <Cards items={data.seasonal} open={open} layout="rail" label="Temporada atual" showOpenOverlay />
      </section>
    </>
  );
}
function Search({
  open,
  preferred,
  initialQuery,
  report,
}: {
  open: (a: Anime) => void;
  preferred?: Anime;
  initialQuery?: string;
  report: (e: unknown) => void;
}) {
  const [q, setQ] = useState(preferred?.title || initialQuery || ""),
    [items, setItems] = useState<Anime[]>([]),
    [page, setPage] = useState(0),
    [next, setNext] = useState(false),
    [busy, setBusy] = useState(false),
    [warnings, setWarnings] = useState<string[]>([]),
    [searched, setSearched] = useState(false);
  const current = useRef("");
  useEffect(
    () => () => {
      if (current.current) api.Cancel(current.current);
    },
    [],
  );
  const search = async (n: number, query = q) => {
    if (current.current) api.Cancel(current.current);
    const id = op();
    current.current = id;
    if (n === 1) {
      setItems([]);
      setWarnings([]);
      setNext(false);
      setSearched(false);
    }
    setBusy(true);
    try {
      const r = await api.Search(id, query, n, n === 1 ? preferred : null);
      if (current.current !== id) return;
      setItems((v) => n === 1 ? r.items : r.items.reduce(upsertSearchAnime, v));
      setPage(n);
      setNext(r.hasNext);
      setWarnings(r.warnings);
      setSearched(true);
    } catch (e) {
      if (current.current === id) report(e);
    } finally {
      if (current.current === id) setBusy(false);
    }
  };
  useEffect(() => {
    const query = preferred?.title || initialQuery;
    if (!query?.trim()) return;
    setQ(query);
    void search(1, query);
  }, [preferred?.id, initialQuery]);
  return (
    <>
      {busy && !items.length && (
        <SearchLoading
          cancel={() => {
            api.Cancel(current.current);
            current.current = "";
            setBusy(false);
          }}
        />
      )}
      {warnings.map((w) => (
        <p key={w}>{w}</p>
      ))}
      <Cards items={items} open={open} showAvailability />
      {busy && items.length > 0 && (
        <div className="search-more-loading" role="status" aria-live="polite" aria-label="Carregando mais resultados">
          <span className="search-loading-spinner" aria-hidden="true" />
          Carregando mais resultados…
        </div>
      )}
      {searched && !items.length && !busy && (
        <Empty>Nenhum anime encontrado. Tente um título alternativo.</Empty>
      )}
      {next && (
        <button disabled={busy} onClick={() => search(page + 1)}>
          Carregar mais
        </button>
      )}
    </>
  );
}

function SearchLoading({ cancel }: { cancel: () => void }) {
  return (
    <section className="search-loading" aria-busy="true">
      <div className="search-loading-status" role="status" aria-live="polite" aria-label="Buscando animes">
        <span className="search-loading-spinner" aria-hidden="true" />
        <div className="search-loading-copy">
          <strong>Buscando animes</strong>
          <span>Consultando fontes e validando episódios…</span>
        </div>
        <button className="search-cancel" type="button" aria-label="Cancelar pesquisa" onClick={cancel}>
          Cancelar
        </button>
      </div>
      <div className="skeleton-grid search-skeleton-grid" aria-hidden="true">
        {Array.from({ length: 10 }, (_, index) => (
          <div className="skeleton-card" key={index}>
            <div className="skeleton poster-skeleton" />
            <div className="skeleton line-skeleton" />
            <div className="skeleton short-skeleton" />
          </div>
        ))}
      </div>
    </section>
  );
}

function upsertSearchAnime(items: Anime[], anime: Anime): Anime[] {
  const index = items.findIndex((item) => key(item) === key(anime) || (item.anilistId > 0 && item.anilistId === anime.anilistId));
  if (index < 0) return [...items, anime];
  const updated = [...items];
  updated[index] = anime;
  return updated;
}
function Details({
  anime,
  favorite,
  saved,
  enqueue,
  report,
  search,
}: {
  anime: Anime;
  favorite: (a: Anime) => Promise<void>;
  saved: boolean;
  enqueue: (d: Detail, ids: Set<string>) => Promise<void>;
  report: (e: unknown) => void;
  search: () => void;
}) {
  const [d, setD] = useState<Detail>(),
    [failed, setFailed] = useState(false),
    [selected, setSelected] = useState(new Set<string>()),
    [season, setSeason] = useState("all"),
    [seasonOpen, setSeasonOpen] = useState(false),
    [playing, setPlaying] = useState("");
  const seasonDropdownRef = useRef<HTMLDivElement>(null);
  const seasonTriggerRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!seasonOpen) return;
    seasonDropdownRef.current
      ?.querySelector<HTMLButtonElement>('[role="option"][aria-selected="true"]')
      ?.focus();
    const closeOutside = (event: PointerEvent) => {
      if (!seasonDropdownRef.current?.contains(event.target as Node)) setSeasonOpen(false);
    };
    const handleKeys = (event: KeyboardEvent) => {
      const options = Array.from(
        seasonDropdownRef.current?.querySelectorAll<HTMLButtonElement>('[role="option"]') ?? [],
      );
      if (!options.length) return;
      const current = options.indexOf(document.activeElement as HTMLButtonElement);
      let next = current;
      if (event.key === "ArrowDown") next = Math.min(current + 1, options.length - 1);
      else if (event.key === "ArrowUp") next = Math.max(current - 1, 0);
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = options.length - 1;
      else if (event.key === "Escape") {
        setSeasonOpen(false);
        seasonTriggerRef.current?.focus();
        return;
      } else return;
      event.preventDefault();
      options[next]?.focus();
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", handleKeys);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", handleKeys);
    };
  }, [seasonOpen]);
  useEffect(() => {
    const id = op();
    api
      .Details(id, anime)
      .then(setD)
      .catch((e) => {
        setFailed(true);
        report(e);
      });
    return () => {
      api.Cancel(id);
    };
  }, [anime.id]);
  if (!d)
    return failed ? (
      <Empty>
        Escolha o título correspondente no catálogo atual.{" "}
        <button onClick={search}>Pesquisar</button>
      </Empty>
    ) : (
      <Busy />
    );
  const episodes = d.episodes.filter((e) =>
    season === "all"
      ? true
      : season === "unknown"
        ? e.season <= 0
        : e.season === Number(season),
  );
  const seasonOptions = [
    { value: "all", label: "Todas" },
    ...(d.episodes.some((e) => e.season <= 0)
      ? [{ value: "unknown", label: "Sem temporada informada" }]
      : []),
    ...[...new Set(d.episodes.map((e) => e.season).filter((n) => n > 0))].map((n) => ({
      value: String(n),
      label: `Temporada ${n}`,
    })),
  ];
  const currentSeasonLabel = seasonOptions.find((option) => option.value === season)?.label ?? "Todas";
  const play = async (i: number) => {
    setPlaying(d.episodes[i].id);
    try {
      await api.Play(op(), d.anime, d.episodes, i, true);
    } catch (e) {
      report(e);
    } finally {
      setPlaying("");
    }
  };
  return (
    <>
      <section className="detail-head anime-detail-hero">
        {d.anime.cover && <Image src={d.anime.cover} alt="" />}
        <div>
          <h1 className="anime-detail-title">{d.anime.title}</h1>
          <div className="anime-detail-meta"><span>{d.episodes.length} episódios</span>{d.anime.status && <span>{d.anime.status}</span>}{d.anime.score > 0 && <span><span className="rating-star" aria-hidden="true">★</span> {d.anime.score.toFixed(1)}</span>}</div>
          <p className="anime-detail-description">{d.anime.description?.replace(/<[^>]*>/g, "")}</p>
          <button
            className="favorite-toggle"
            type="button"
            aria-label={saved ? "Remover da Minha Lista" : "Adicionar à Minha Lista"}
            aria-pressed={saved}
            title={saved ? "Remover da Minha Lista" : "Adicionar à Minha Lista"}
            onClick={() => favorite(anime).catch(report)}
          >
            <NavIcon name="list" />
          </button>
        </div>
      </section>
      <div className="toolbar episode-toolbar">
        <div className="season-filter">
          <span>Temporada</span>
          <div
            className="season-dropdown"
            ref={seasonDropdownRef}
            onBlur={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setSeasonOpen(false);
            }}
          >
            <button
              ref={seasonTriggerRef}
              className="season-trigger"
              type="button"
              aria-label={`Temporada: ${currentSeasonLabel}`}
              aria-haspopup="listbox"
              aria-expanded={seasonOpen}
              aria-controls="season-options"
              onClick={() => setSeasonOpen((open) => !open)}
            >
              <span>{currentSeasonLabel}</span>
              <svg aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="m4 6 4 4 4-4" />
              </svg>
            </button>
            {seasonOpen && (
              <div className="season-options" id="season-options" role="listbox" aria-label="Filtrar por temporada">
                {seasonOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    role="option"
                    aria-selected={season === option.value}
                    onClick={() => {
                      setSeason(option.value);
                      setSeasonOpen(false);
                      seasonTriggerRef.current?.focus();
                    }}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <span className="episode-result-count">{episodes.length} episódios</span>
        <div className="episode-selection-actions">
          <button onClick={() => setSelected((current) => {
            const next = new Set(current);
            episodes.forEach((episode) => next.add(episode.id));
            return next;
          })}>
            Selecionar exibidos
          </button>
          <button disabled={!selected.size} onClick={() => setSelected(new Set())}>Limpar</button>
        </div>
        <button className="download-selected"
          disabled={!selected.size}
          onClick={() => enqueue(d, selected).catch(report)}
        >
          Baixar selecionados{selected.size ? ` · ${selected.size}` : ""}
        </button>
      </div>
      {playing && <Busy cancel={() => api.Cancel("play")} />}
      <ol className="episodes">
        {episodes.map((ep) => (
          <li className="episode-row" key={ep.id}>
            <input
              aria-label={`Selecionar episódio ${ep.number}`}
              type="checkbox"
              checked={selected.has(ep.id)}
              onChange={(e) => setSelected((current) => {
                const next = new Set(current);
                e.target.checked ? next.add(ep.id) : next.delete(ep.id);
                return next;
              })}
            />
            <div className="episode-info">
              <span className="episode-number">{ep.season > 0 ? `T${ep.season} · ` : ""}{ep.number > 0 ? `Episódio ${ep.number}` : "Episódio"}</span>
              {ep.title && <strong title={ep.title}>{ep.title}</strong>}
            </div>
            <small className="episode-audio">{ep.audio}</small>
            <div className="episode-actions">
              <button className="episode-watch" onClick={() => play(d.episodes.findIndex((x) => x.id === ep.id))}>Assistir</button>
              <button className="episode-download" aria-label={`Baixar episódio ${ep.number}`} title="Baixar episódio" onClick={() => enqueue(d, new Set([ep.id])).catch(report)}><NavIcon name="downloads" /></button>
            </div>
          </li>
        ))}
      </ol>
      {!d.episodes.length && (
        <Empty>Este título ainda não tem episódios disponíveis.</Empty>
      )}
    </>
  );
}
function HistoryView({
  open,
  search,
  report,
  limit,
  variant = "list",
  showOpenOverlay = false,
}: {
  open: (a: Anime) => void;
  search?: (a: Anime) => void;
  report: (e: unknown) => void;
  limit?: number;
  variant?: "list" | "shelf";
  showOpenOverlay?: boolean;
}) {
  const [h, setH] = useState<History[]>(), [resuming, setResuming] = useState(""), [page, setPage] = useState(1), [recoveredCovers, setRecoveredCovers] = useState<Record<string, string>>({}), [failedCovers, setFailedCovers] = useState<Record<string, boolean>>({});
  const recoverCover = (title: string, historyKey: string, request = op(), preferredAniListID = 0) => {
    api.Preview(request, title, preferredAniListID).then((metadata) => {
      if (!metadata.cover) return;
      setRecoveredCovers((covers) => ({ ...covers, [historyKey]: metadata.cover }));
      setFailedCovers((current) => ({ ...current, [historyKey]: false }));
      void api.SaveHistoryCover(historyKey, metadata.cover).catch(() => {});
    }).catch(() => {});
    return request;
  };
  const load = () => api.History().then(setH).catch(report);
  useEffect(() => {
    load();
  }, []);
  const sorted = h?.slice().sort((a, b) => b.updated - a.updated) || [];
  const pageCount = Math.max(1, Math.ceil(sorted.length / HISTORY_PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const recent = variant === "shelf"
    ? sorted.slice(0, limit ?? sorted.length)
    : sorted.slice((currentPage - 1) * HISTORY_PAGE_SIZE, currentPage * HISTORY_PAGE_SIZE);
  useEffect(() => {
    if (!h) return;
    const requests = recent
      .filter((x) => !x.anime.cover && x.anime.provider !== "local")
      .map((x) => {
        const id = op();
        return recoverCover(x.anime.title, key(x.anime), id, x.anime.anilistId || 0);
      });
    return () => requests.forEach((id) => api.Cancel(id));
  }, [h, variant, limit, currentPage]);
  if (!h) return variant === "shelf" ? null : <Busy />;
  if (variant === "shelf") {
    if (!recent.length) return null;
    return (
      <section className="home-shelf continue-shelf">
        <div className="shelf-heading"><h3>Continuar assistindo</h3></div>
        <Rail label="Continuar assistindo">
          {recent.map((x) => {
            const id = key(x.anime);
            const anime = (!x.anime.cover || failedCovers[id]) && recoveredCovers[id] ? { ...x.anime, cover: recoveredCovers[id] } : x.anime;
            return <Card
              key={id}
              a={anime}
              open={() => open(anime)}
              showOpenOverlay={showOpenOverlay}
              subtitle={x.needsResolve ? "Histórico antigo" : `T${x.episode.season} · Ep. ${x.episode.number} · ${time(x.position)}`}
              onImageFailure={() => {
                setFailedCovers((current) => ({ ...current, [id]: true }));
                if (x.anime.provider !== "local" && !recoveredCovers[id]) recoverCover(x.anime.title, id, undefined, x.anime.anilistId || 0);
              }}
              action={!x.needsResolve ? <>
                <button className="continue-action" disabled={resuming !== ""} onClick={async () => {
                  setResuming(id);
                  try { await api.Resume(op(), id); } catch(e) { report(e); } finally { setResuming(""); }
                }}>
                  <NavIcon name="play" />
                  {resuming === id ? "Abrindo…" : "Continuar"}
                </button>
              </> : undefined}
            />;
          })}
        </Rail>
      </section>
    );
  }
  return (
    <section className="history-page" aria-label="Histórico de animes">
      <div className="history-heading"><h3>Assistidos recentemente</h3><span>{h.length} títulos</span></div>
      {!h.length && <Empty>Os episódios assistidos aparecerão aqui.</Empty>}
      {pageCount > 1 && (
        <HistoryPagination
          currentPage={currentPage}
          pageCount={pageCount}
          total={sorted.length}
          onPageChange={setPage}
          position="top"
        />
      )}
      <div className="history-grid">
        {recent.map((x) => {
          const id = key(x.anime);
          const anime = (!x.anime.cover || failedCovers[id]) && recoveredCovers[id] ? { ...x.anime, cover: recoveredCovers[id] } : x.anime;
          const episode = x.needsResolve
            ? "Episódio antigo · encontre onde parou"
            : [x.episode.season > 0 ? `Temporada ${x.episode.season}` : "", x.episode.number > 0 ? `Episódio ${x.episode.number}` : x.episode.title || "", time(x.position)].filter(Boolean).join(" · ");
          return (
            <article className="history-card" key={id}>
              <button className="history-poster" aria-label={`Abrir ${x.anime.title}`} onClick={() => x.needsResolve ? (search || open)(anime) : open(anime)}>
                {anime.cover && !failedCovers[id] ? <Image src={anime.cover} alt="" loading="lazy" onLoadFailure={() => {
                  setFailedCovers((current) => ({ ...current, [id]: true }));
                  if (x.anime.provider !== "local" && !recoveredCovers[id]) recoverCover(x.anime.title, id, undefined, x.anime.anilistId || 0);
                }} /> : <span className="history-poster-placeholder">AC</span>}
              </button>
              <div className="history-card-copy">
                <strong title={x.anime.title}>{x.anime.title}</strong>
                <small>{episode}</small>
                <div className="history-card-actions">
                  {x.needsResolve ? (
                    <button className="history-primary" onClick={() => (search || open)(anime)}>Encontrar episódios</button>
                  ) : (
                    <button className="history-primary" disabled={resuming !== ""} onClick={async () => {
                      setResuming(id);
                      try { await api.Resume(op(), id); } catch(e) { report(e); } finally { setResuming(""); }
                    }}>
                      <NavIcon name="play" />
                      {resuming === id ? "Abrindo…" : "Continuar"}
                    </button>
                  )}
                  <button className="history-remove" aria-label={`Remover ${x.anime.title} do histórico`} title="Remover do histórico" onClick={() => api.RemoveHistory(id).then(load).catch(report)}>×</button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
      {pageCount > 1 && (
        <HistoryPagination
          currentPage={currentPage}
          pageCount={pageCount}
          total={sorted.length}
          onPageChange={setPage}
          position="bottom"
        />
      )}
    </section>
  );
}
function HistoryPagination({
  currentPage,
  pageCount,
  total,
  onPageChange,
  position,
}: {
  currentPage: number;
  pageCount: number;
  total: number;
  onPageChange: (page: number) => void;
  position: "top" | "bottom";
}) {
  const first = (currentPage - 1) * HISTORY_PAGE_SIZE + 1;
  const last = Math.min(currentPage * HISTORY_PAGE_SIZE, total);
  return (
    <nav className={`history-pagination ${position}`} aria-label={`Paginação do histórico ${position === "top" ? "superior" : "inferior"}`}>
      <span>Mostrando {first}–{last} de {total}</span>
      <div>
        <button
          className="history-page-button"
          type="button"
          aria-label="Página anterior"
          disabled={currentPage <= 1}
          onClick={() => onPageChange(currentPage - 1)}
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m12 4-6 6 6 6" /></svg>
        </button>
        <span aria-live="polite">Página {currentPage} de {pageCount}</span>
        <button
          className="history-page-button"
          type="button"
          aria-label="Próxima página"
          disabled={currentPage >= pageCount}
          onClick={() => onPageChange(currentPage + 1)}
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m8 4 6 6-6 6" /></svg>
        </button>
      </div>
    </nav>
  );
}
function Queue({
  items,
  report,
  loading = false,
  openAnime,
}: {
  items: Download[];
  report: (e: unknown) => void;
  loading?: boolean;
  openAnime: (a: Anime) => void;
}) {
  const active = (status: string) => ["queued", "resolving", "downloading"].includes(status);
  const statusLabel: Record<string, string> = { queued: "Na fila", resolving: "Preparando", downloading: "Baixando", done: "Concluído", failed: "Falhou", error: "Falhou", canceled: "Cancelado", cancelled: "Cancelado", interrupted: "Interrompido" };
  if (loading) return <div className="download-skeletons" role="status" aria-label="Carregando downloads">{[0, 1, 2].map((i) => <div className="download-skeleton" key={i}><div className="skeleton download-thumb-skeleton" /><div className="download-skeleton-lines"><div className="skeleton line-skeleton" /><div className="skeleton short-skeleton" /><div className="skeleton progress-skeleton" /></div></div>)}</div>;
  if (!items.length) return <div className="queue-empty"><NavIcon name="downloads" /><strong>Nenhum download</strong><span>Os episódios que você baixar aparecerão aqui.</span></div>;
  return (
    <div className="download-list">
      {items.map((d) => (
        <article className="job" key={d.id}>
          <div className="job-main">
            {d.anime.cover ? <Image className="job-cover" src={d.anime.cover} alt="" loading="lazy" /> : <div className="job-cover job-cover-placeholder">AC</div>}
            <div className="job-info">
              <strong className="job-title" title={d.anime.title}>{d.anime.title}</strong>
              <span className="job-episode">{d.episode.season > 0 ? `Temporada ${d.episode.season} · ` : ""}{d.episode.number > 0 ? `Episódio ${d.episode.number}` : d.episode.title || "Episódio"}{d.episode.audio ? ` · ${d.episode.audio}` : ""}</span>
              <div className="job-progress"><progress aria-label="Progresso do download" className={active(d.status) && d.status !== "downloading" ? "indeterminate" : ""} value={Math.max(0, Math.min(100, d.percent || 0))} max="100" /><span>{Math.round(d.percent || 0)}%</span></div>
              <div className="job-meta"><span>{statusLabel[d.status] || d.status}</span>{d.speed && active(d.status) && <span>{d.speed}</span>}{d.eta && active(d.status) && <span>Restam {d.eta}</span>}</div>
            </div>
          </div>
          {d.error && <p className="job-error" role="alert">{userMessage(d.error)}</p>}
          <div className="job-actions">
            {d.kind !== "manga" && d.anime.provider !== "local" && <button className="job-open" onClick={() => openAnime(d.anime)}>Abrir anime</button>}
            {active(d.status) && <button className="job-cancel" onClick={() => api.CancelDownload(d.id).catch(report)}>Cancelar</button>}
          </div>
        </article>
      ))}
    </div>
  );
}
function DownloadsView({
  queue,
  report,
  openAnime,
  reader,
}: {
  queue: Download[];
  report: (e: unknown) => void;
  openAnime: (a: Anime) => void;
  reader: (pages: string[]) => void;
}) {
  const [files, setFiles] = useState<LocalFile[]>([]);
  const load = () => api.LocalFiles().then(setFiles).catch(report);
  useEffect(() => {
    load();
  }, [queue.filter((x) => x.status === "done").length]);
  return (
    <>
      <div className="toolbar downloads-toolbar">
        <button
          className="downloads-toolbar-action"
          type="button"
          aria-label="Abrir pasta de downloads"
          title="Abrir pasta de downloads"
          onClick={() => api.OpenDownloads().catch(report)}
        >
          <NavIcon name="folderOpen" />
        </button>
        <button
          className="downloads-toolbar-action"
          type="button"
          aria-label="Atualizar biblioteca"
          title="Atualizar biblioteca"
          onClick={load}
        >
          <NavIcon name="refresh" />
        </button>
      </div>
      <Queue items={queue} report={report} openAnime={openAnime} />
      <h3>Disponíveis offline</h3>
      {!files.length && <Empty>Seus downloads aparecerão nesta pasta.</Empty>}
      {files.map((f) => (
        <div className="row" key={f.path}>
          {f.cover && <Image src={f.cover} alt="" style={{width:48,height:68,objectFit:"cover"}} />}
          <span>
            {f.title} · {f.kind === "manga" ? "CBZ" : `Ep. ${f.episode}`} ·{" "}
            {(f.size / 1024 / 1024).toFixed(1)} MB
          </span>
          <div className="local-file-actions">
            <button
              className="local-file-action"
              type="button"
              aria-label={f.kind === "manga" ? `Ler ${f.title}` : `Reproduzir ${f.title}`}
              title={f.kind === "manga" ? "Ler" : "Reproduzir"}
              onClick={() => {
                if (f.kind === "manga") {
                  api.OfflinePages(f.path).then(reader).catch(report);
                } else api.PlayLocal(f.path).catch(report);
              }}
            >
              <NavIcon name={f.kind === "manga" ? "manga" : "play"} />
            </button>
            <button
              className="local-file-action"
              type="button"
              aria-label={`Abrir pasta de ${f.title}`}
              title="Abrir pasta"
              onClick={() => api.OpenLocalFolder(f.path).catch(report)}
            >
              <NavIcon name="folder" />
            </button>
            <button
              className="local-file-action local-file-delete"
              type="button"
              aria-label={`Excluir ${f.title}`}
              title="Excluir"
              onClick={() => {
                if (window.confirm(`Excluir o arquivo ${f.title}?`))
                  api.DeleteFile(f.path).then(load).catch(report);
              }}
            >
              <NavIcon name="trash" />
            </button>
          </div>
        </div>
      ))}
    </>
  );
}
function MangaCover({ manga, className = "" }: { manga: Manga; className?: string }) {
  const [failed, setFailed] = useState(!manga.cover);
  return failed ? (
    <span className={`manga-cover-placeholder ${className}`} aria-hidden="true">
      {manga.title.slice(0, 1).toLocaleUpperCase() || "漫"}
    </span>
  ) : (
    <Image className={className} src={manga.cover} alt={`Capa de ${manga.title}`} loading="lazy" onLoadFailure={() => setFailed(true)} />
  );
}

const mangaStatus = (status: string) =>
  ({ ongoing: "Em publicação", completed: "Concluído", hiatus: "Em pausa", cancelled: "Cancelado" }[status] || status || "Status não informado");

function MangaRailCard({ manga, label, index, open }: { manga: Manga; label: string; index: number; open: (manga: Manga) => void }) {
  const [preview, setPreview] = useState(false);
  const [previewStyle, setPreviewStyle] = useState<CSSProperties>();
  const previewId = useId();
  const cardRef = useRef<HTMLButtonElement>(null);
  const showTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const positionPreview = () => {
    const card = cardRef.current;
    if (!card || window.innerWidth <= 760 || window.innerHeight < 220) return undefined;
    const rect = card.getBoundingClientRect();
    const margin = 16;
    const gap = 12;
    const width = Math.min(280, window.innerWidth - margin * 2);
    const maxHeight = Math.min(200, window.innerHeight - margin * 2);
    const rightSpace = window.innerWidth - rect.right - gap - margin;
    const leftSpace = rect.left - gap - margin;
    const placeRight = rightSpace >= width || rightSpace >= leftSpace;
    const panelWidth = Math.min(width, Math.max(0, placeRight ? rightSpace : leftSpace));
    const left = placeRight ? rect.right + gap : rect.left - gap - panelWidth;
    const top = Math.max(margin, Math.min(rect.top + Math.min(24, rect.height * .12), window.innerHeight - maxHeight - margin));
    const theme = getComputedStyle(card.closest(".app") || card);
    return {
      position: "fixed",
      left: Math.max(margin, Math.min(left, window.innerWidth - panelWidth - margin)),
      top,
      width: panelWidth,
      maxHeight,
      "--surface-raised": theme.getPropertyValue("--surface-raised"),
      "--text": theme.getPropertyValue("--text"),
      "--border": theme.getPropertyValue("--border"),
      "--shadow": theme.getPropertyValue("--shadow"),
      "--accent": theme.getPropertyValue("--accent"),
      "--muted": theme.getPropertyValue("--muted"),
    } as CSSProperties;
  };
  const showPreview = () => {
    if (window.innerWidth <= 760) return;
    if (showTimer.current) clearTimeout(showTimer.current);
    if (closeTimer.current) clearTimeout(closeTimer.current);
    showTimer.current = setTimeout(() => {
      const style = positionPreview();
      if (!style) return;
      setPreviewStyle(style);
      setPreview(true);
    }, 450);
  };
  const hidePreview = () => {
    if (showTimer.current) clearTimeout(showTimer.current);
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => {
      setPreview(false);
      setPreviewStyle(undefined);
    }, 180);
  };
  const keepPreviewOpen = () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
  };
  useEffect(() => () => {
    if (showTimer.current) clearTimeout(showTimer.current);
    if (closeTimer.current) clearTimeout(closeTimer.current);
  }, []);
  useEffect(() => {
    if (!preview) return;
    let frame = 0;
    const reposition = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const style = positionPreview();
        if (style) setPreviewStyle(style);
        else setPreview(false);
      });
    };
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [preview]);

  const summary = manga.description?.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  return <>
    <button
      ref={cardRef}
      type="button"
      className="manga-shelf-card"
      aria-describedby={preview ? previewId : undefined}
      onClick={() => open(manga)}
      onMouseEnter={showPreview}
      onMouseLeave={hidePreview}
      onFocus={showPreview}
      onBlur={hidePreview}
    >
      <span className="manga-shelf-poster">
        <MangaCover manga={manga} />
        {label === "Top mangás" && <span className="manga-rank" aria-label={`Posição ${index + 1}`}>{index + 1}</span>}
        <span className="manga-poster-overlay" aria-hidden="true" />
        <span className="manga-poster-cta" aria-hidden="true">Ver mangá <NavIcon name="arrow" /></span>
      </span>
      <span className="manga-shelf-title" title={manga.title}>{manga.title}</span>
      <small className="manga-shelf-meta">{mangaStatus(manga.status)}</small>
    </button>
    {preview && previewStyle && createPortal(
      <div className="preview manga-preview" id={previewId} role="tooltip" style={previewStyle} onMouseEnter={keepPreviewOpen} onMouseLeave={hidePreview}>
        <strong className="preview-title">{manga.title}</strong>
        {summary && <p className="preview-description">{summary}</p>}
      </div>,
      document.body,
    )}
  </>;
}

function MangaRail({ items, label, open }: { items: Manga[]; label: string; open: (manga: Manga) => void }) {
  return (
    <Rail label={label}>
      {items.map((manga, index) => <MangaRailCard key={manga.id} manga={manga} label={label} index={index} open={open} />)}
    </Rail>
  );
}

function MangaView({
  open,
  resume,
  initialQuery,
  sharedQuery,
  syncQuery,
  report,
}: {
  open: (m: Manga) => void;
  resume: (p: MangaProgress) => void;
  initialQuery?: string;
  sharedQuery: string;
  syncQuery: (query: string) => void;
  report: (e: unknown) => void;
}) {
  const [items, setItems] = useState<Manga[]>([]),
    [history, setHistory] = useState<MangaProgress[]>([]),
    [busy, setBusy] = useState(false),
    [searched, setSearched] = useState(false),
    [submittedQuery, setSubmittedQuery] = useState(""),
    [searchError, setSearchError] = useState(""),
    [discovery, setDiscovery] = useState<MangaDiscovery>(),
    [discoveryBusy, setDiscoveryBusy] = useState(true),
    [discoveryError, setDiscoveryError] = useState(""),
    [activeCategory, setActiveCategory] = useState<MangaCategory>(),
    [spot, setSpot] = useState(0),
    [heroImageFailed, setHeroImageFailed] = useState(false),
    [heroCoverFallback, setHeroCoverFallback] = useState(false);
  const id = useRef(""), discoveryID = useRef("");
  const loadDiscovery = async () => {
    if (discoveryID.current) void api.Cancel(discoveryID.current).catch(() => {});
    const requestID = op();
    discoveryID.current = requestID;
    setDiscoveryBusy(true);
    setDiscoveryError("");
    try {
      const result = await api.MangaDiscover(requestID);
      if (discoveryID.current !== requestID) return;
      setDiscovery(result);
      setDiscoveryError("");
    } catch (error) {
      if (discoveryID.current === requestID) setDiscoveryError(message(error));
    } finally {
      if (discoveryID.current === requestID) setDiscoveryBusy(false);
    }
  };
  useEffect(() => {
    let active = true;
    api.MangaHistory().then((entries) => { if (active) setHistory(entries); }).catch(report);
    void loadDiscovery();
    return () => {
      active = false;
      if (id.current) void api.Cancel(id.current).catch(() => {});
      if (discoveryID.current) {
        const requestID = discoveryID.current;
        discoveryID.current = "";
        void api.Cancel(requestID).catch(() => {});
      }
    };
  }, []);
  const search = async (value = sharedQuery) => {
    const query = value.trim();
    if (id.current) void api.Cancel(id.current).catch(() => {});
    id.current = "";
    if (!query) {
      setItems([]);
      setSearched(false);
      setSearchError("Digite o título do mangá para pesquisar.");
      setBusy(false);
      return;
    }
    id.current = op();
    const current = id.current;
    setBusy(true);
    setSearched(true);
    setSubmittedQuery(query);
    setActiveCategory(undefined);
    setSearchError("");
    setItems([]);
    try {
      const result = await api.MangaSearch(current, query);
      if (current === id.current) setItems(result);
    } catch (e) {
      if (current === id.current) setSearchError(message(e));
    } finally {
      if (current === id.current) setBusy(false);
    }
  };
  const clearSearch = () => {
    if (id.current) void api.Cancel(id.current).catch(() => {});
    id.current = "";
    syncQuery("");
    setItems([]);
    setSearched(false);
    setActiveCategory(undefined);
    setSearchError("");
    setBusy(false);
  };
  const browseCategory = async (category: MangaCategory) => {
    if (id.current) void api.Cancel(id.current).catch(() => {});
    id.current = op();
    const requestID = id.current;
    syncQuery("");
    setBusy(true);
    setSearched(true);
    setSubmittedQuery("");
    setActiveCategory(category);
    setSearchError("");
    setItems([]);
    try {
      const result = await api.MangaByCategory(requestID, category.id);
      if (id.current === requestID) setItems(result);
    } catch (error) {
      if (id.current === requestID) setSearchError(message(error));
    } finally {
      if (id.current === requestID) setBusy(false);
    }
  };
  const updateQuery = (value: string) => {
    syncQuery(value);
    if (searchError) setSearchError("");
  };
  useEffect(() => {
    const query = initialQuery?.trim();
    if (!query) return;
    syncQuery(query);
    void search(query);
  }, [initialQuery]);
  const featured = discovery?.featured || [];
  const spotlight = featured[spot % Math.max(1, featured.length)];
  useEffect(() => { setHeroImageFailed(false); setHeroCoverFallback(false); }, [spotlight?.id]);
  useEffect(() => {
    const count = Math.min(5, featured.length);
    if (count < 2) return;
    const timer = window.setInterval(() => setSpot((value) => (value + 1) % count), 7000);
    return () => window.clearInterval(timer);
  }, [featured.length]);
  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable=true]")) return;
      const rail = target?.closest<HTMLElement>(".cards.rail");
      if (rail) {
        event.preventDefault();
        rail.scrollBy({ left: (event.key === "ArrowRight" ? 1 : -1) * Math.max(240, rail.clientWidth * .75), behavior: "smooth" });
        return;
      }
      if (target?.closest(".manga-spotlight") || target === document.body) {
        const count = Math.min(5, featured.length);
        if (!count) return;
        event.preventDefault();
        setSpot((value) => (value + (event.key === "ArrowRight" ? 1 : -1) + count) % count);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [featured.length]);
  return (
    <section className="manga-library" aria-label="Biblioteca de mangás">
      <section className="spotlight manga-spotlight" aria-labelledby="manga-discovery-title">
        {spotlight && !heroImageFailed && (spotlight.banner || spotlight.cover) && <Image className="spotlight-image" src={heroCoverFallback ? spotlight.cover : spotlight.banner || spotlight.cover} alt="" onLoadFailure={() => {
          if (!heroCoverFallback && spotlight.banner && spotlight.cover && spotlight.banner !== spotlight.cover) setHeroCoverFallback(true);
          else setHeroImageFailed(true);
        }} />}
        <div className="spotlight-shade" aria-hidden="true" />
        <div className="spotlight-copy">
          <span className="spotlight-eyebrow">MANGÁS PARA DESCOBRIR</span>
          <h2 id="manga-discovery-title" title={spotlight?.title}>{spotlight?.title || "Sua próxima história começa aqui"}</h2>
          <p>{spotlight?.description?.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, 220) || "Encontre uma obra, explore gêneros e continue a leitura de onde parou."}</p>
          {spotlight && <button type="button" className="spotlight-action" onClick={() => open(spotlight)}><NavIcon name="manga" /> Ver mangá</button>}
        </div>
        {featured.length > 1 && <div className="spotlight-dots" role="group" aria-label="Destaques de mangás">
          {featured.map((manga, index) => <button type="button" key={manga.id} aria-label={`Destaque ${index + 1}: ${manga.title}`} aria-pressed={spot === index} onClick={() => setSpot(index)}><span /></button>)}
        </div>}
      </section>
      {discovery?.warning && <p className="manga-discovery-warning" role="status">Algumas prateleiras não puderam ser atualizadas. {discovery.warning}</p>}
      {discoveryError && !discovery && <div className="manga-inline-error" role="alert"><span>Não foi possível carregar o catálogo de descoberta.</span><button type="button" onClick={() => void loadDiscovery()}>Tentar novamente</button></div>}
      {busy && <div className="manga-status" role="status" aria-live="polite"><span className="search-loading-spinner" />Buscando no catálogo…</div>}
      {searchError && <div className="manga-inline-error" role="alert"><span>{searchError}</span>{activeCategory ? <button type="button" onClick={() => void browseCategory(activeCategory)}>Tentar novamente</button> : sharedQuery.trim() && <button type="button" onClick={() => void search()}>Tentar novamente</button>}</div>}
      {!busy && searched && !searchError && items.length === 0 && <div className="manga-welcome manga-empty-results"><span className="manga-welcome-icon"><NavIcon name="search" /></span><strong>Nenhum mangá encontrado</strong><p>{activeCategory ? "Não há obras disponíveis nesta categoria agora." : `Não encontramos “${submittedQuery}”. Tente outro título ou uma forma alternativa de escrita.`}</p><button type="button" onClick={clearSearch}>Voltar ao catálogo</button></div>}
      {items.length > 0 && (
        <section className="manga-results-section" aria-label="Resultados de mangá">
          <div className="manga-section-heading">
            <div><span className="manga-eyebrow">CATÁLOGO</span><h2>{activeCategory ? activeCategory.name : `Resultados para “${submittedQuery}”`}</h2><small>{items.length} {items.length === 1 ? "obra encontrada" : "obras encontradas"}</small></div>
            <button type="button" className="manga-clear-search" onClick={clearSearch}>Limpar busca</button>
          </div>
          <div className="manga-results">
            {items.map((manga) => (
              <button type="button" className="manga-result-card" key={manga.id} onClick={() => open(manga)}>
                <MangaCover manga={manga} />
                <span className="manga-result-copy"><strong>{manga.title}</strong><span className="manga-result-meta"><small>{mangaStatus(manga.status)}</small>{manga.languages?.slice(0, 2).map((language) => <small className="manga-language-tag" key={language}>{language.toLocaleUpperCase()}</small>)}</span>{manga.description && <small className="manga-result-description">{manga.description}</small>}</span>
                <span className="manga-card-action">Ver capítulos <NavIcon name="arrow" /></span>
              </button>
            ))}
          </div>
        </section>
      )}
      {history.length > 0 && (
        <section className="home-shelf manga-history" aria-label="Continuar lendo">
          <div className="shelf-heading"><h3>Continue lendo</h3><span className="manga-section-count">{history.length} {history.length === 1 ? "leitura" : "leituras"}</span></div>
          <Rail label="Continue lendo">
            {history.slice().sort((a, b) => b.updated - a.updated).map((progress) => (
              <article className="card manga-history-card" key={progress.manga.id}>
                <button type="button" onClick={() => resume(progress)}>
                  <span className="card-poster"><MangaCover manga={progress.manga} /></span>
                  <strong className="card-title" title={progress.manga.title}>{progress.manga.title}</strong>
                  <small className="card-subtitle">Cap. {progress.chapter.number || progress.chapter.title || "—"} · Página {progress.page + 1}{progress.chapter.pages > 0 ? ` de ${progress.chapter.pages}` : ""}</small>
                </button>
                {progress.chapter.pages > 0 && <progress className="manga-history-progress" value={Math.min(progress.page + 1, progress.chapter.pages)} max={progress.chapter.pages} aria-label={`Progresso em ${progress.manga.title}`} />}
                <div className="card-actions"><button type="button" className="continue-action" onClick={() => resume(progress)}><NavIcon name="play" />Continuar lendo</button></div>
              </article>
            ))}
          </Rail>
        </section>
      )}
      {!searched && <section className="manga-category-section" aria-labelledby="manga-category-title">
        <div className="manga-category-heading">
          <div className="manga-category-heading-copy"><span className="manga-eyebrow">CATÁLOGO</span><h3 id="manga-category-title">Categorias</h3></div>
          {(discovery?.categories.length || 0) > 0 && <span className="manga-section-count">{discovery!.categories.length} gêneros</span>}
        </div>
        <div className="manga-category-list" role="group" aria-label="Filtrar mangás por categoria">
          {(discovery?.categories || []).map((category, index) => <button type="button" className="manga-category-chip" aria-label={category.name} key={category.id} onClick={() => void browseCategory(category)}>
            <span className="manga-category-number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
            <strong className="manga-category-name">{category.name}</strong>
            <span className="manga-category-action" aria-hidden="true"><NavIcon name="arrow" /></span>
          </button>)}
          {discoveryBusy && !discovery && <span className="manga-category-loading">Carregando categorias…</span>}
        </div>
      </section>}
      {!searched && discoveryBusy && !discovery && <div className="manga-discovery-loading" role="status" aria-label="Carregando recomendações"><div className="skeleton-grid">{Array.from({ length: 6 }, (_, index) => <div className="skeleton-card" key={index}><div className="skeleton poster-skeleton" /><div className="skeleton line-skeleton" /><div className="skeleton short-skeleton" /></div>)}</div></div>}
      {!searched && discovery && <>
        {discovery.popular.length > 0 && <section className="home-shelf manga-shelf-section" aria-labelledby="manga-top-title"><div className="shelf-heading"><h3 id="manga-top-title">Top mangás</h3></div><MangaRail items={discovery.popular} label="Top mangás" open={open} /></section>}
        {discovery.recentlyUpdated.length > 0 && <section className="home-shelf manga-shelf-section" aria-labelledby="manga-updated-title"><div className="shelf-heading"><h3 id="manga-updated-title">Em alta</h3></div><MangaRail items={discovery.recentlyUpdated} label="Em alta" open={open} /></section>}
        {discovery.publishing.length > 0 && <section className="home-shelf manga-shelf-section" aria-labelledby="manga-publishing-title"><div className="shelf-heading"><h3 id="manga-publishing-title">Em publicação</h3></div><MangaRail items={discovery.publishing} label="Em publicação" open={open} /></section>}
      </>}
      {!searched && history.length === 0 && !busy && !discoveryBusy && discovery && discovery.popular.length === 0 && discovery.recentlyUpdated.length === 0 && discovery.publishing.length === 0 && <div className="manga-welcome manga-first-visit"><span className="manga-welcome-icon"><NavIcon name="manga" /></span><strong>Comece explorando o catálogo</strong><p>Busque pelo nome de uma obra ou escolha uma categoria para encontrar capítulos e abrir o leitor.</p></div>}
      <footer className="manga-credit">Catálogo e leitura fornecidos pelo <button type="button" onClick={() => desktop().OpenLink("https://mangadex.org")}>MangaDex</button>.</footer>
    </section>
  );
}
function ChaptersView({
  manga,
  open,
  report,
  showQueue,
}: {
  manga: Manga;
  open: (c: Chapter, chapters: Chapter[]) => void;
  report: (e: unknown) => void;
  showQueue: () => void;
}) {
  const [chapters, setChapters] = useState<Chapter[] | null>(null),
    [language, setLanguage] = useState(""),
    [chapterError, setChapterError] = useState(""),
    [selected, setSelected] = useState(new Set<string>()),
    [descending, setDescending] = useState(false),
    [retry, setRetry] = useState(0),
    [downloading, setDownloading] = useState(false);
  useEffect(() => {
    const id = op();
    let active = true;
    setChapters(null);
    setChapterError("");
    setSelected(new Set());
    const request = language ? api.ChaptersLanguage(id, manga.id, language) : api.Chapters(id, manga.id);
    request.then((items) => { if (active) setChapters(items); }).catch((e) => {
      if (active) { setChapterError(message(e)); setChapters([]); }
    });
    return () => {
      active = false;
      void api.Cancel(id).catch(() => {});
    };
  }, [manga.id, language, retry]);
  const ordered = (chapters || []).slice();
  if (descending) ordered.reverse();
  const allSelected = ordered.length > 0 && ordered.every((chapter) => selected.has(chapter.id));
  const download = async (list: Chapter[]) => {
    setDownloading(true);
    try {
      await api.DownloadManga(op(), manga, list);
      showQueue();
    } catch (e) { report(e); }
    finally { setDownloading(false); }
  };
  return (
    <section className="manga-chapters" aria-label={`Capítulos de ${manga.title}`}>
      <header className="manga-detail-head">
        <MangaCover manga={manga} />
        <div><span className="manga-eyebrow">MANGÁ</span><h1>{manga.title}</h1><p>{manga.description || "Sinopse não disponível."}</p><small>{mangaStatus(manga.status)}</small></div>
      </header>
      <section className="manga-chapter-panel" aria-label="Lista de capítulos">
        <div className="manga-chapter-heading"><div><h2>Capítulos</h2><small>{chapters === null ? "Carregando catálogo…" : `${ordered.length} disponíveis`}</small></div></div>
        <div className="manga-chapter-toolbar">
          <label>Idioma
            <select aria-label="Idioma dos capítulos" value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="">Automático · preferir português</option>
              {[...new Set([...(manga.languages || []), "pt-br", "en", "es-la", "es"])].sort().map((code) => <option key={code} value={code}>{code.toLocaleUpperCase()}</option>)}
            </select>
          </label>
          <button type="button" onClick={() => setDescending((value) => !value)}>{descending ? "Mais antigos primeiro" : "Mais recentes primeiro"}</button>
          <button type="button" disabled={!ordered.length} onClick={() => setSelected(allSelected ? new Set() : new Set(ordered.map((chapter) => chapter.id)))}>{allSelected ? "Limpar seleção" : "Selecionar todos"}</button>
          <button type="button" className="manga-download-selected" disabled={!selected.size || downloading} onClick={() => void download(ordered.filter((chapter) => selected.has(chapter.id)))}>{downloading ? "Enfileirando…" : `Baixar selecionados${selected.size ? ` (${selected.size})` : ""}`}</button>
        </div>
        {chapters === null && <Busy />}
        {chapterError && <div className="manga-inline-error" role="alert"><span>Não foi possível carregar os capítulos: {chapterError}</span><button type="button" onClick={() => setRetry((value) => value + 1)}>Tentar novamente</button></div>}
        {chapters?.length === 0 && !chapterError && <Empty>Não há capítulos disponíveis neste idioma. Tente outra tradução.</Empty>}
        {ordered.length > 0 && <div className="manga-chapter-list">
          {ordered.map((chapter, index) => (
            <article className="manga-chapter-row" key={chapter.id}>
              <label className="manga-chapter-check"><input type="checkbox" aria-label={`Selecionar capítulo ${chapter.number || index + 1}`} checked={selected.has(chapter.id)} onChange={(e) => setSelected((current) => { const next = new Set(current); e.target.checked ? next.add(chapter.id) : next.delete(chapter.id); return next; })} /></label>
              <div className="manga-chapter-copy"><strong>{chapter.number ? `Capítulo ${chapter.number}` : chapter.title || `Capítulo ${index + 1}`}</strong><small>{[chapter.volume && `Volume ${chapter.volume}`, chapter.title, chapter.language?.toUpperCase(), chapter.pages && `${chapter.pages} páginas`, chapter.group && `Grupo: ${chapter.group}`].filter(Boolean).join(" · ")}</small></div>
              <div className="manga-chapter-actions"><button type="button" className="manga-read-button" onClick={() => open(chapter, ordered)}>Ler capítulo</button><button type="button" onClick={() => void download([chapter])}>Baixar CBZ</button></div>
            </article>
          ))}
        </div>}
      </section>
    </section>
  );
}
function Reader({
  route,
  report,
  back,
  changeChapter,
}: {
  route: Route;
  report: (e: unknown) => void;
  back: () => void;
  changeChapter: (chapter: Chapter, chapters: Chapter[]) => void;
}) {
  const [pages, setPages] = useState<string[]>([]),
    [page, setPage] = useState(Math.max(0, route.page || 0)),
    [loading, setLoading] = useState(!!route.chapter),
    [loadError, setLoadError] = useState(""),
    [retry, setRetry] = useState(0),
    [failedPages, setFailedPages] = useState(new Set<number>()),
    [chapterOptions, setChapterOptions] = useState(route.chapters || []),
    [mode, setMode] = useState<"vertical" | "paged">(() => localStorage.getItem("animecaos-manga-reader-mode") === "paged" ? "paged" : "vertical"),
    [direction, setDirection] = useState<"rtl" | "ltr">(() => localStorage.getItem("animecaos-manga-reader-direction") === "ltr" ? "ltr" : "rtl");
  const container = useRef<HTMLDivElement>(null),
    progressRef = useRef<MangaProgress | null>(null),
    chapterID = route.chapter?.id || "";
  const scrollToPage = (index: number, behavior: ScrollBehavior = "auto") => {
    const element = container.current?.querySelector(`[data-page="${index}"]`) as HTMLElement | null;
    if (element && typeof element.scrollIntoView === "function") element.scrollIntoView({ behavior, block: "start" });
  };
  useEffect(() => {
    let active = true;
    if (!chapterID) {
      setPages(route.pages || []);
      setLoading(false);
      setLoadError("");
      setPage(Math.min(route.page || 0, Math.max(0, (route.pages || []).length - 1)));
      return () => { active = false; };
    }
    const id = op();
    setLoading(true);
    setLoadError("");
    setPages([]);
    setFailedPages(new Set());
    setPage(Math.max(0, route.page || 0));
    api.Pages(id, chapterID).then((result) => {
      if (!active) return;
      if (!result.length) throw new Error("O capítulo não retornou páginas.");
      setPages(result);
      setPage(Math.min(route.page || 0, result.length - 1));
      setLoading(false);
    }).catch((e) => {
      if (active) { setLoadError(message(e)); setPages([]); setLoading(false); }
    });
    return () => {
      active = false;
      void api.Cancel(id).catch(() => {});
    };
  }, [chapterID, retry]);
  useEffect(() => {
    if (!route.manga || !route.chapter || route.chapters?.length) {
      setChapterOptions(route.chapters || []);
      return;
    }
    const id = op();
    let active = true;
    const request = route.chapter.language ? api.ChaptersLanguage(id, route.manga.id, route.chapter.language) : api.Chapters(id, route.manga.id);
    request.then((result) => { if (active) setChapterOptions(result); }).catch(() => {});
    return () => { active = false; void api.Cancel(id).catch(() => {}); };
  }, [route.manga?.id, route.chapter?.language, route.chapters]);
  useEffect(() => {
    if (!pages.length || mode === "paged") return;
    const target = Math.min(page, pages.length - 1);
    scrollToPage(target);
  }, [pages, mode]);
  useEffect(() => {
    if (!pages.length || mode !== "vertical") return;
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) setPage(Number((visible.target as HTMLElement).dataset.page));
    }, { threshold: [0.25, 0.55, 0.8] });
    container.current?.querySelectorAll("[data-page]").forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [pages, mode]);
  const currentProgress: MangaProgress | null = route.manga && route.chapter && pages.length ? { manga: route.manga, chapter: route.chapter, page, updated: 0 } : null;
  useEffect(() => {
    progressRef.current = currentProgress;
    if (!currentProgress) return;
    const timer = window.setTimeout(() => api.SaveMangaProgress(currentProgress).catch(report), 350);
    return () => window.clearTimeout(timer);
  }, [route.manga?.id, chapterID, page, pages.length]);
  useEffect(() => () => {
    if (progressRef.current) void api.SaveMangaProgress(progressRef.current).catch(() => {});
  }, []);
  const movePage = (delta: number) => {
    const next = Math.max(0, Math.min(pages.length - 1, page + delta));
    if (next === page) return;
    setPage(next);
    if (mode === "vertical") scrollToPage(next, "smooth");
  };
  useEffect(() => {
    if (mode !== "paged") return;
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(target.tagName)) return;
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        const forward = direction === "rtl" ? event.key === "ArrowLeft" : event.key === "ArrowRight";
        movePage(forward ? 1 : -1);
      } else if (event.key === "PageDown" || event.key === " ") {
        event.preventDefault(); movePage(1);
      } else if (event.key === "PageUp") {
        event.preventDefault(); movePage(-1);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mode, direction, page, pages.length]);
  const currentChapterIndex = route.chapter ? chapterOptions.findIndex((chapter) => chapter.id === route.chapter?.id) : -1;
  const previousChapter = currentChapterIndex > 0 ? chapterOptions[currentChapterIndex - 1] : undefined;
  const nextChapter = currentChapterIndex >= 0 ? chapterOptions[currentChapterIndex + 1] : undefined;
  const visiblePages = mode === "paged" ? pages.slice(page, page + 1) : pages;
  const reloadChapter = () => { setLoadError(""); setFailedPages(new Set()); setRetry((value) => value + 1); };
  return (
    <section className="manga-reader" aria-label="Leitor de mangá">
      <div className="reader-topbar">
        <button type="button" className="reader-back" onClick={back}>← <span>Capítulos</span></button>
        <div className="reader-title"><strong>{route.manga?.title || "Leitura offline"}</strong><small>{route.chapter ? `Cap. ${route.chapter.number || route.chapter.title || "—"}${route.chapter.language ? ` · ${route.chapter.language.toUpperCase()}` : ""}` : "Arquivo local"}</small></div>
        <div className="reader-chapter-nav"><button type="button" aria-label="Capítulo anterior" title="Capítulo anterior" disabled={!previousChapter} onClick={() => previousChapter && changeChapter(previousChapter, chapterOptions)}>‹</button><button type="button" aria-label="Próximo capítulo" title="Próximo capítulo" disabled={!nextChapter} onClick={() => nextChapter && changeChapter(nextChapter, chapterOptions)}>›</button></div>
      </div>
      <div className="reader-tools">
        <button type="button" aria-label="Página anterior" title="Página anterior" disabled={!pages.length || page <= 0} onClick={() => movePage(-1)}>‹</button>
        <label className="reader-page-select">Página <select aria-label="Ir para página" disabled={!pages.length} value={pages.length ? Math.min(page, pages.length - 1) : 0} onChange={(event) => { const next = Number(event.target.value); setPage(next); scrollToPage(next, "smooth"); }}>{pages.map((_, index) => <option key={index} value={index}>{index + 1}</option>)}</select><span>de {pages.length || "—"}</span></label>
        <button type="button" aria-label="Próxima página" title="Próxima página" disabled={!pages.length || page >= pages.length - 1} onClick={() => movePage(1)}>›</button>
        <label className="reader-mode-select">Leitura <select aria-label="Modo de leitura" value={mode} onChange={(event) => { const value = event.target.value as "vertical" | "paged"; setMode(value); localStorage.setItem("animecaos-manga-reader-mode", value); }}><option value="vertical">Rolagem contínua</option><option value="paged">Uma página por vez</option></select></label>
        {mode === "paged" && <label className="reader-direction-select">Ordem <select aria-label="Direção de leitura" value={direction} onChange={(event) => { const value = event.target.value as "rtl" | "ltr"; setDirection(value); localStorage.setItem("animecaos-manga-reader-direction", value); }}><option value="rtl">Direita para esquerda</option><option value="ltr">Esquerda para direita</option></select></label>}
      </div>
      {loading && <div className="reader-state" role="status"><Busy /><span>Carregando páginas do capítulo…</span></div>}
      {!loading && loadError && <div className="reader-state reader-error" role="alert"><strong>Não foi possível abrir este capítulo.</strong><span>{loadError}</span><button type="button" onClick={reloadChapter}>Tentar novamente</button></div>}
      {!loading && !loadError && pages.length === 0 && <Empty>Este arquivo não contém páginas para exibir.</Empty>}
      {!!pages.length && <div className={`reader-pages reader-${mode}`} ref={container}>
        {visiblePages.map((url, visibleIndex) => {
          const index = mode === "paged" ? page : visibleIndex;
          return <article key={`${chapterID}:${url}`} id={`manga-page-${index + 1}`} data-page={index} className="manga-page">
            {failedPages.has(index) ? <div className="reader-page-error" role="alert"><strong>Página {index + 1} indisponível</strong><span>O servidor de imagens não respondeu. Recarregue o capítulo para buscar uma nova rota.</span><button type="button" onClick={reloadChapter}>Recarregar capítulo</button></div> : <img src={url} alt={`Página ${index + 1}`} loading={mode === "paged" || index < 2 || Math.abs(index - page) < 2 ? "eager" : "lazy"} decoding="async" onError={() => setFailedPages((current) => new Set(current).add(index))} onLoad={() => setFailedPages((current) => { if (!current.has(index)) return current; const next = new Set(current); next.delete(index); return next; })} />}
          </article>;
        })}
      </div>}
      {!!pages.length && <div className="reader-bottom-nav"><button type="button" disabled={!previousChapter} onClick={() => previousChapter && changeChapter(previousChapter, chapterOptions)}>← Capítulo anterior</button><span>{page + 1} / {pages.length}</span><button type="button" disabled={!nextChapter} onClick={() => nextChapter && changeChapter(nextChapter, chapterOptions)}>Próximo capítulo →</button></div>}
    </section>
  );
}
function AccountsPanel({ compact = false }: { compact?: boolean }) {
  const [accounts, setAccounts] = useState<Account[]>([]),
    [busy, setBusy] = useState(""),
    [loginInProgress, setLoginInProgress] = useState(false),
    [accountsLoaded, setAccountsLoaded] = useState(false),
    [error, setError] = useState("");
  const load = async () => {
    try {
      setAccounts(await api.Accounts());
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAccountsLoaded(true);
    }
  };
  useEffect(() => { void load(); }, []);
  const connect = async (provider: string) => {
    setBusy(provider);
    setLoginInProgress(true);
    setError("");
    try {
      await api.Login("login", provider);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      try { setAccounts(await api.Accounts()); } catch { /* keep the login error visible */ }
    } finally {
      setBusy("");
      setLoginInProgress(false);
    }
  };
  const refresh = async (provider: string) => {
    setBusy(provider);
    setError("");
    try {
      const updated = await api.RefreshAccount(op(), provider);
      setAccounts((current) => current.map((account) => account.provider === provider ? updated : account));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  };
  const disconnect = async (provider: string) => {
    setBusy(provider);
    setError("");
    try {
      await api.Logout(provider);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  };
  const providers = [
    { id: "discord", name: "Discord", icon: "/discord.svg", description: "Vincule sua conta para identificar seu perfil no AnimeCaos.", tracksProgress: false },
    { id: "anilist", name: "AniList", icon: "/anilist.ico", description: "Sincronize seu progresso com o AniList.", tracksProgress: true },
    { id: "mal", name: "MyAnimeList", icon: "/myanimelist.ico", description: "Sincronize seu progresso com o MyAnimeList.", tracksProgress: true },
  ];
  return (
    <div className={`account-connections${compact ? " account-connections-compact" : ""}`}>
      <div className="account-provider-grid">
        {providers.map((provider) => {
          const account = accounts.find((item) => item.provider === provider.id);
          const connected = !!account?.connected;
          return (
            <article className="account-provider" key={provider.id} aria-busy={busy === provider.id}>
              <header className="account-provider-heading">
                <img className={`account-provider-icon${provider.id === "discord" ? " discord-provider-icon" : ""}`} src={provider.icon} alt={`${provider.name} logo`} />
                <div className="account-provider-brand">
                  <h3>{provider.name}</h3>
                  <p className={account?.error && !connected ? "account-provider-error" : ""}>
                    {connected ? account?.name || "Conta conectada" : account?.error || provider.description}
                  </p>
                </div>
                <span className={`account-provider-status${connected ? " is-connected" : ""}`}>
                  {!accountsLoaded ? "Verificando…" : connected ? "Conectada" : "Desconectada"}
                </span>
              </header>
              {connected ? (
                <>
                  {provider.tracksProgress && <p className="account-provider-stats">
                    {account?.animeCount ?? 0} animes · {account?.episodes ?? 0} episódios · {Math.round((account?.minutes ?? 0) / 60)} h
                  </p>}
                  <div className="account-provider-actions">
                    <button type="button" className="settings-secondary" disabled={!!busy} onClick={() => void refresh(provider.id)}>
                      {busy === provider.id ? "Atualizando…" : "Atualizar perfil"}
                    </button>
                    <button type="button" className="settings-secondary" disabled={!!busy} onClick={() => void disconnect(provider.id)}>Desconectar</button>
                  </div>
                </>
              ) : (
                <button type="button" className="settings-secondary account-connect-button" disabled={!!busy || !accountsLoaded} onClick={() => void connect(provider.id)}>
                  {busy === provider.id ? "Aguardando autorização…" : `Conectar ${provider.name}`}
                </button>
              )}
              {provider.id === "discord" && <p className="account-provider-note">O vínculo identifica seu perfil; a presença é controlada separadamente em Configurações. Episódios assistidos são sincronizados pelo AniList/MAL.</p>}
            </article>
          );
        })}
      </div>
      {error && <p className="account-connection-error" role="alert">{error}</p>}
      {loginInProgress && <button type="button" className="account-cancel-login" onClick={() => api.Cancel("login").catch((e) => setError(String(e)))}>Cancelar login</button>}
      <p className="account-sync-note">AniList e MyAnimeList são atualizados quando o episódio termina ou quando você assiste pelo menos 80% dele, se o título tiver correspondência no serviço. O login do Discord identifica o perfil; a presença depende do Discord Desktop aberto.</p>
    </div>
  );
}

function AccountsView() {
  return <section className="accounts-view"><header><h3>Contas conectadas</h3><p>Vincule seu perfil Discord e sincronize episódios assistidos no AniList ou MyAnimeList.</p></header><AccountsPanel /></section>;
}

function SettingsAccountSummary({ navigate }: { navigate: (name: string) => void }) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  useEffect(() => {
    let active = true;
    api.Accounts().then((items) => { if (active) setAccounts(items); }).catch(() => { if (active) setLoadFailed(true); }).finally(() => { if (active) setLoaded(true); });
    return () => { active = false; };
  }, []);
  const providers = [
    { id: "discord", name: "Discord", icon: "/discord.svg" },
    { id: "anilist", name: "AniList", icon: "/anilist.ico" },
    { id: "mal", name: "MyAnimeList", icon: "/myanimelist.ico" },
  ];
  return (
    <div className="settings-account-summary" aria-label="Estado das contas">
      {providers.map((provider) => {
        const account = accounts.find((item) => item.provider === provider.id);
        const connected = !!account?.connected;
        return <div className="settings-account-row" key={provider.id}>
          <img src={provider.icon} alt="" />
          <span>{provider.name}</span>
          <small className={connected ? "is-connected" : ""}>{!loaded ? "Verificando…" : loadFailed ? "Não disponível" : connected ? account?.name || "Conectada" : "Desconectada"}</small>
        </div>;
      })}
      {loadFailed && <p role="alert">Não foi possível consultar o estado das contas.</p>}
      <p>AniList e MyAnimeList sincronizam episódios concluídos ou assistidos em pelo menos 80%, quando há correspondência.</p>
      <button type="button" className="settings-secondary settings-link-button" onClick={() => navigate("accounts")}>Gerenciar contas <NavIcon name="arrow" /></button>
    </div>
  );
}

function SettingsSwitch({
  label,
  description,
  checked,
  onChange,
  icon,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  icon?: ReactNode;
}) {
  return <label className="settings-switch-row">
    <span className="settings-switch-copy">
      {icon}
      <span><strong>{label}</strong><small>{description}</small></span>
    </span>
    <input type="checkbox" role="switch" aria-label={label} checked={checked} onChange={(event) => onChange(event.target.checked)} />
    <span className="settings-switch-track" aria-hidden="true"><span /></span>
  </label>;
}

function SettingsView({
  settings,
  onChange,
  saveState,
  retrySave,
  report,
  navigate,
}: {
  settings: Settings;
  onChange: (s: Partial<Settings>, immediate?: boolean) => void;
  saveState: "idle" | "saving" | "saved" | "error";
  retrySave: () => void;
  report: (e: unknown) => void;
  navigate: (name: string) => void;
}) {
  const v = settings;
  const [update, setUpdate] = useState<Update>(),
    [packagePath, setPackage] = useState(""),
    [toolStatus, setToolStatus] = useState(""),
    [toolError, setToolError] = useState(false),
    [checkingUpdate, setCheckingUpdate] = useState(false),
    [downloadsDraft, setDownloadsDraft] = useState(v.downloadsDir),
    [activeSection, setActiveSection] = useState("settings-appearance");
  const patch = (x: Partial<Settings>) => onChange(x);
  useEffect(() => setDownloadsDraft(v.downloadsDir), [v.downloadsDir]);
  useEffect(() => {
    const main = document.querySelector("main");
    if (!main) return;
    const updateActive = () => {
      const threshold = main.getBoundingClientRect().top + 150;
      const sections = ["settings-appearance", "settings-playback", "settings-downloads", "settings-integrations", "settings-maintenance"];
      let current = sections[0];
      for (const id of sections) {
        const element = document.getElementById(id);
        if (element && element.getBoundingClientRect().top <= threshold) current = id;
      }
      setActiveSection(current);
    };
    updateActive();
    main.addEventListener("scroll", updateActive, { passive: true });
    window.addEventListener("resize", updateActive);
    return () => { main.removeEventListener("scroll", updateActive); window.removeEventListener("resize", updateActive); };
  }, []);
  const sectionLinks = [
    ["settings-appearance", "Aparência"], ["settings-playback", "Reprodução"], ["settings-downloads", "Downloads"], ["settings-integrations", "Integrações"], ["settings-maintenance", "Manutenção"],
  ] as const;
  const scrollToSection = (id: string) => {
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    document.getElementById(id)?.scrollIntoView({ behavior: reduceMotion ? "instant" : "smooth", block: "start" });
    setActiveSection(id);
  };
  const runTool = async (success: string, action: () => Promise<unknown>) => {
    setToolStatus("");
    setToolError(false);
    try { await action(); setToolStatus(success); }
    catch (error) { setToolError(true); setToolStatus(userMessage(message(error))); }
  };
  return (
    <div className="settings-page">
      <div className="settings-intro">
        <div>
          <h3>Configurações</h3>
          <p>Preferências do app, reprodução e integrações.</p>
        </div>
        <div className="settings-save-state-wrap">
          {saveState === "saving" && <span className="settings-save-state is-saving" role="status">Salvando…</span>}
          {saveState === "saved" && <span className="settings-save-state is-saved" role="status">Salvo</span>}
          {saveState === "error" && <div className="settings-save-error" role="alert">Não foi possível salvar. <button type="button" onClick={retrySave}>Tentar novamente</button></div>}
        </div>
      </div>

      <nav className="settings-index" aria-label="Índice das configurações">
        {sectionLinks.map(([id, label]) => <button type="button" key={id} className={activeSection === id ? "active" : ""} aria-current={activeSection === id ? "location" : undefined} onClick={() => scrollToSection(id)}>{label}</button>)}
      </nav>

      <div className="settings-sections">
        <SettingsSection id="settings-appearance" icon="settings" title="Aparência" description="Deixe a interface do seu jeito.">
          <div className="settings-fields settings-fields-columns">
            <div className="settings-field">
              <span className="settings-field-label" id="settings-theme-label">Tema</span>
              <div className="settings-theme-options" role="group" aria-labelledby="settings-theme-label">
                {([["system", "Sistema"], ["light", "Claro"], ["dark", "Escuro"]] as const).map(([value, label]) => <button type="button" key={value} aria-pressed={(v.theme || "system") === value} onClick={() => patch({ theme: value })}>{label}</button>)}
              </div>
            </div>
            <div className="settings-field">
              <label className="settings-field-label" htmlFor="settings-scale">Escala da interface</label>
              <div className="settings-range">
                <input id="settings-scale" type="range" min="1" max="1.5" step="0.05" value={v.uiScale} onChange={(e) => patch({ uiScale: +e.target.value })} />
                <output className="settings-range-value" htmlFor="settings-scale">{Math.round(v.uiScale * 100)}%</output>
              </div>
            </div>
          </div>
        </SettingsSection>

        <SettingsSection id="settings-playback" icon="play" title="Reprodução" description="Escolha como o anime deve tocar.">
          <div className="settings-fields settings-fields-columns">
            <div className="settings-field">
              <label className="settings-field-label" htmlFor="settings-player">Player</label>
              <select id="settings-player" value={v.playerMode} onChange={(e) => patch({ playerMode: e.target.value })}>
                <option value="mpv">MPV integrado</option>
                <option value="system">Player padrão do sistema</option>
                <option value="custom">Player personalizado</option>
              </select>
            </div>
            {v.playerMode === "custom" && (
              <div className="settings-field">
                <label className="settings-field-label" htmlFor="settings-player-path">Executável</label>
                <div className="settings-input-action">
                  <input id="settings-player-path" value={v.playerPath} onChange={(e) => patch({ playerPath: e.target.value })} />
                  <button type="button" className="settings-secondary" onClick={() => desktop().ChoosePlayer().then((p) => p && patch({ playerPath: p })).catch(report)}>Escolher</button>
                </div>
              </div>
            )}
            <div className="settings-field">
              <label className="settings-field-label" htmlFor="settings-audio">Áudio preferido</label>
              <select id="settings-audio" value={v.audio} onChange={(e) => patch({ audio: e.target.value })}>
                <option value="legendado">Legendado</option>
                <option value="dublado">Dublado</option>
              </select>
            </div>
            <SettingsSwitch label="Próximo episódio automático" description="Continuar quando o episódio terminar." checked={v.autoplay} onChange={(checked) => patch({ autoplay: checked })} />
            {v.playerMode !== "mpv" && <p className="settings-note">Os controles no app e a reprodução automática requerem o MPV.</p>}
          </div>
        </SettingsSection>

        <SettingsSection id="settings-downloads" icon="downloads" title="Downloads" description="Organize onde e como os arquivos são baixados.">
          <div className="settings-fields settings-fields-columns">
            <div className="settings-field settings-field-wide">
              <label className="settings-field-label" htmlFor="settings-downloads-dir">Pasta de downloads</label>
              <div className="settings-input-action">
                <input id="settings-downloads-dir" value={downloadsDraft} onChange={(e) => setDownloadsDraft(e.target.value)} onBlur={() => { if (downloadsDraft !== v.downloadsDir) patch({ downloadsDir: downloadsDraft }); }} onKeyDown={(event) => { if (event.key === "Enter") event.currentTarget.blur(); }} />
                <button type="button" className="settings-secondary" onClick={() => desktop().ChooseDirectory().then((p) => { if (p) { setDownloadsDraft(p); patch({ downloadsDir: p }); } }).catch(report)}>Escolher pasta</button>
              </div>
            </div>
            <div className="settings-field">
              <label className="settings-field-label" htmlFor="settings-concurrent">Downloads simultâneos</label>
              <input id="settings-concurrent" type="number" min="1" max="5" value={v.concurrent} onChange={(e) => { const value = Number(e.target.value); if (Number.isInteger(value) && value >= 1 && value <= 5) patch({ concurrent: value }); }} />
              <small>Entre 1 e 5 tarefas.</small>
            </div>
            <SettingsSwitch label="Fechar painel ao concluir" description="Ocultar downloads quando a fila terminar." checked={v.autoClose} onChange={(checked) => patch({ autoClose: checked })} />
            {v.autoClose && (
              <div className="settings-field">
                <label className="settings-field-label" htmlFor="settings-close-delay">Aguardar antes de fechar</label>
                <div className="settings-number-suffix"><input id="settings-close-delay" type="number" min="0" max="60000" step="500" value={v.autoCloseMs} onChange={(e) => { const value = Number(e.target.value); if (Number.isInteger(value) && value >= 0 && value <= 60000) patch({ autoCloseMs: value }); }} /><span>ms</span></div>
              </div>
            )}
          </div>
        </SettingsSection>

        <SettingsSection id="settings-integrations" icon="list" title="Integrações" description="Sincronize seu progresso e compartilhe o que está assistindo.">
          <div className="settings-fields">
            <SettingsSwitch label="Discord Rich Presence" description="Mostre AnimeCaos, anime, episódio e tempo no Discord Desktop." checked={v.discord} onChange={(checked) => patch({ discord: checked })} icon={<span className="settings-discord-icon"><img src="/discord.svg" alt="" /></span>} />
            <SettingsAccountSummary navigate={navigate} />
          </div>
        </SettingsSection>

        <SettingsSection id="settings-maintenance" icon="history" title="Manutenção" description="Ferramentas para manter o app atualizado.">
          <div className="settings-tools">
            <button type="button" className="settings-secondary" onClick={() => void runTool("Cache de metadados limpo.", () => api.ClearCache())}>Limpar cache de metadados</button>
            <button type="button" className="settings-secondary" disabled={checkingUpdate} onClick={() => { setToolStatus(""); setToolError(false); setUpdate(undefined); setCheckingUpdate(true); api.CheckUpdate(op()).then((result) => { setUpdate(result); setToolStatus(result.available ? `Versão ${result.version} disponível.` : result.managed ? "As atualizações são gerenciadas pelo Flatpak." : "O app está atualizado."); }).catch((error) => { setToolError(true); setToolStatus(userMessage(message(error))); }).finally(() => setCheckingUpdate(false)); }}>{checkingUpdate ? "Verificando…" : "Verificar atualização"}</button>
            <button type="button" className="settings-secondary settings-link-button" onClick={() => navigate("logs")}>Abrir diagnóstico <NavIcon name="arrow" /></button>
          </div>
          {toolStatus && <p className={`settings-tool-status${toolError ? " is-error" : ""}`} role={toolError ? "alert" : "status"}>{toolStatus}</p>}
          {update && (
            <div className="settings-update" role="status">
              <strong>{update.managed ? "Atualize pelo Flatpak." : update.available ? `Versão ${update.version} disponível.` : "Você está na versão mais recente."}</strong>
              {update.notes && <pre>{update.notes}</pre>}
              {update.available && !update.managed && <button type="button" className="settings-secondary" onClick={() => void runTool("Atualização baixada e verificada.", async () => setPackage(await api.DownloadUpdate(op(), update)))}>Baixar e verificar</button>}
              {packagePath && <div className="settings-input-action"><small className="settings-package-path">Pacote verificado: {packagePath}</small><button type="button" className="settings-secondary" onClick={() => void runTool("O instalador foi iniciado.", () => api.InstallUpdate(packagePath))}>Instalar e reiniciar</button></div>}
            </div>
          )}
        </SettingsSection>
      </div>
    </div>
  );
}

function SettingsSection({ id, icon, title, description, children }: { id: string; icon: string; title: string; description: string; children: ReactNode }) {
  return (
    <section className="settings-section" id={id} aria-labelledby={`settings-heading-${title.toLowerCase().replace(/\s+/g, "-")}`}>
      <header className="settings-section-heading">
        <span className="settings-section-icon"><NavIcon name={icon} /></span>
        <div><h4 id={`settings-heading-${title.toLowerCase().replace(/\s+/g, "-")}`}>{title}</h4><p>{description}</p></div>
      </header>
      {children}
    </section>
  );
}
function Diagnostics({
  logs,
  report,
}: {
  logs: string[];
  report: (e: unknown) => void;
}) {
  const [data, setData] = useState<unknown>();
  useEffect(() => {
    api.Diagnose().then(setData).catch(report);
  }, []);
  return (
    <>
      <h3>Dependências e dados</h3>
      <pre>{JSON.stringify(data, null, 2)}</pre>
      <h3>Eventos desta sessão</h3>
      <pre>{logs.join("\n") || "Nenhum erro registrado nesta sessão."}</pre>
    </>
  );
}
