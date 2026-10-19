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
  type Chapter,
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
  history: "M3 12a9 9 0 1 0 2.6-6.4L3 8m0-5v5h5m4-1v5l3 2",
  downloads: "M12 3v12m-5-5 5 5 5-5M4 19v2h16v-2",
  manga: "M4 4.5A2.5 2.5 0 0 1 6.5 2H20v18H6.5A2.5 2.5 0 0 1 4 17.5v-13ZM4 16h16M8 6h8m-8 3h8",
  settings: "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7ZM19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.7 2.9-.2-.1a1.7 1.7 0 0 0-1.9.2l-.2.1h-3.4l-.1-.2a1.7 1.7 0 0 0-1.7-1l-.2.1-2.9-1.7.1-.2a1.7 1.7 0 0 0-.2-1.9l-.1-.2v-3.4l.2-.1a1.7 1.7 0 0 0 1-1.7l-.1-.2 1.7-2.9.2.1a1.7 1.7 0 0 0 1.9-.2l.2-.1h3.4l.1.2a1.7 1.7 0 0 0 1.7 1l.2-.1 2.9 1.7-.1.2a1.7 1.7 0 0 0 .2 1.9l.1.2v3.4l-.2.1",
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
  const focusHomeSearch = () => {
    if (route.name !== "home") navigate({ name: "home" });
    window.setTimeout(() => {
      const input = document.querySelector<HTMLInputElement>(".header-search input");
      input?.focus();
      input?.select();
    }, 0);
  };
  useEffect(() => {
    setHeaderQuery(route.name === "search" ? route.query || route.anime?.title || "" : "");
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
        <img src="/animecaos-icon.png" alt="" className="boot-logo" />
        <h1>AnimeCaos</h1>
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
        <div className="brand"><img src="/animecaos-icon.png" alt="" /><h1>AnimeCaos</h1><SidebarToggle collapsed={sidebarCollapsed} onClick={toggleSidebar} /></div>
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
            if (route.name === "search") {
              setRoute({ name: "search", query });
              setError("");
            } else navigate({ name: "search", query });
          }}>
            <NavIcon name="search" />
            <input type="search" aria-label="Buscar animes" placeholder="Buscar animes..." value={headerQuery} onChange={(e) => setHeaderQuery(e.target.value)} />
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
              report={report}
            />
          )}
          {route.name === "chapters" && route.manga && (
            <ChaptersView
              manga={route.manga}
              open={(c) =>
                navigate({ name: "reader", manga: route.manga, chapter: c })
              }
              report={report}
              showQueue={() => setPanel(true)}
            />
          )}
          {route.name === "reader" && <Reader route={route} report={report} />}
          {route.name === "accounts" && <AccountsView report={report} />}
          {route.name === "settings" && (
            <SettingsView
              settings={settings}
              navigate={(name) => navigate({ name })}
              save={async (v) => {
                await api.SaveSettings(v);
                localStorage.setItem("animecaos-theme", v.theme || "system");
                setSettings(v);
              }}
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
              onChange={(e) =>
                run(async () => {
                  const v = { ...settings, autoplay: e.target.checked };
                  await api.SaveSettings(v);
                  setSettings(v);
                })
              }
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
function Cards({ items, open, layout = "grid", label = "Animes", showAvailability = false }: { items: Anime[]; open: (a: Anime) => void; layout?: "grid" | "rail"; label?: string; showAvailability?: boolean }) {
  const cards = items.map((a) => <Card key={key(a)} a={a} open={() => open(a)} showAvailability={showAvailability} />);
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
function Card({ a, open, subtitle, action, onImageFailure, showAvailability = false }: { a: Anime; open: () => void; subtitle?: string; action?: ReactNode; onImageFailure?: () => void; showAvailability?: boolean }) {
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
        .Preview(id, a.title)
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
        </span>
        <strong className="card-title" title={a.title}>{a.title}</strong>
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
      <HistoryView limit={8} variant="shelf" open={openHistory} report={report} />
      <section className="home-shelf">
        <div className="shelf-heading"><h3>Em alta</h3></div>
        <Cards items={data.trending} open={open} layout="rail" label="Em alta" />
      </section>
      <section className="home-shelf">
        <div className="shelf-heading"><h3>Temporada atual</h3></div>
        <Cards items={data.seasonal} open={open} layout="rail" label="Temporada atual" />
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
}: {
  open: (a: Anime) => void;
  search?: (a: Anime) => void;
  report: (e: unknown) => void;
  limit?: number;
  variant?: "list" | "shelf";
}) {
  const [h, setH] = useState<History[]>(), [resuming, setResuming] = useState(""), [page, setPage] = useState(1), [recoveredCovers, setRecoveredCovers] = useState<Record<string, string>>({}), [failedCovers, setFailedCovers] = useState<Record<string, boolean>>({});
  const recoverCover = (title: string, historyKey: string, request = op()) => {
    api.Preview(request, title).then((metadata) => {
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
        return recoverCover(x.anime.title, key(x.anime), id);
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
              subtitle={x.needsResolve ? "Histórico antigo" : `T${x.episode.season} · Ep. ${x.episode.number} · ${time(x.position)}`}
              onImageFailure={() => {
                setFailedCovers((current) => ({ ...current, [id]: true }));
                if (x.anime.provider !== "local" && !recoveredCovers[id]) recoverCover(x.anime.title, id);
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
                  if (x.anime.provider !== "local" && !recoveredCovers[id]) recoverCover(x.anime.title, id);
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
      <div className="toolbar">
        <button onClick={() => api.OpenDownloads().catch(report)}>
          Abrir pasta
        </button>
        <button onClick={load}>Atualizar biblioteca</button>
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
function MangaView({
  open,
  resume,
  report,
}: {
  open: (m: Manga) => void;
  resume: (p: MangaProgress) => void;
  report: (e: unknown) => void;
}) {
  const [q, setQ] = useState(""),
    [items, setItems] = useState<Manga[]>([]),
    [history, setHistory] = useState<MangaProgress[]>([]),
    [busy, setBusy] = useState(false);
  const id = useRef("");
  const search = async () => {
    if (id.current) api.Cancel(id.current);
    id.current = op();
    const current = id.current;
    setBusy(true);
    try {
      const r = await api.MangaSearch(current, q);
      if (current === id.current) setItems(r);
    } catch (e) {
      report(e);
    } finally {
      if (current === id.current) setBusy(false);
    }
  };
  useEffect(() => {
    search();
    api.MangaHistory().then(setHistory).catch(report);
    return () => {
      api.Cancel(id.current);
    };
  }, []);
  return (
    <>
      <form
        className="search"
        onSubmit={(e) => {
          e.preventDefault();
          search();
        }}
      >
        <input
          type="search"
          aria-label="Título do mangá"
          placeholder="Pesquisar no MangaDex"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button>Pesquisar</button>
      </form>
      {history.length > 0 && (
        <>
          <h3>Continuar lendo</h3>
          {history.map((p) => (
            <button key={p.manga.id} onClick={() => resume(p)}>
              {p.manga.title} · Cap. {p.chapter.number || p.chapter.title} ·
              Pág. {p.page + 1}
            </button>
          ))}
        </>
      )}
      {busy && <Busy cancel={() => api.Cancel(id.current)} />}
      <div className="cards">
        {items.map((m) => (
          <button className="card" key={m.id} onClick={() => open(m)}>
            <Image src={m.cover} alt="" loading="lazy" />
            <strong>{m.title}</strong>
            <small>{m.status}</small>
          </button>
        ))}
      </div>
      {!busy && !items.length && <Empty>Nenhum mangá encontrado.</Empty>}
    </>
  );
}
function ChaptersView({
  manga,
  open,
  report,
  showQueue,
}: {
  manga: Manga;
  open: (c: Chapter) => void;
  report: (e: unknown) => void;
  showQueue: () => void;
}) {
  const [chapters, setChapters] = useState<Chapter[]>(),
    [language, setLanguage] = useState(""),
    [chapterError, setChapterError] = useState(""),
    [selected, setSelected] = useState(new Set<string>());
  useEffect(() => {
    const id = op();
    let active = true;
    setChapters(undefined);
    setChapterError("");
    setSelected(new Set());
    const request = language ? api.ChaptersLanguage(id, manga.id, language) : api.Chapters(id, manga.id);
    request.then((items) => { if (active) setChapters(items); }).catch((e) => {
      if (active) { setChapterError(String(e)); setChapters([]); }
    });
    return () => {
      active = false;
      api.Cancel(id);
    };
  }, [manga.id, language]);
  const filtered = chapters || [];
  const download = (list: Chapter[]) => {
    showQueue();
    api.DownloadManga(op(), manga, list).catch(report);
  };
  return (
    <>
      <p>{manga.description}</p>
      <div className="toolbar">
        <label>
          Idioma{" "}
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            <option value="">Automático (preferir português)</option>
            {[...new Set([...(manga.languages || []), "pt-br", "en", "es-la", "es"])].sort().map((l) => (
              <option key={l}>{l}</option>
            ))}
          </select>
        </label>
        <button onClick={() => setSelected(new Set(filtered.map((c) => c.id)))}>
          Selecionar todos
        </button>
        <button
          disabled={!selected.size}
          onClick={() => download(filtered.filter((c) => selected.has(c.id)))}
        >
          Baixar selecionados
        </button>
      </div>
      {!chapters && <Busy />}
      {chapterError && <Empty>{chapterError}</Empty>}
      {chapters?.length === 0 && !chapterError && (
        <Empty>Sem capítulos disponíveis neste idioma.</Empty>
      )}
      {filtered.map((c) => (
        <div className="row" key={c.id}>
          <input
            type="checkbox"
            aria-label={`Selecionar capítulo ${c.number}`}
            checked={selected.has(c.id)}
            onChange={(e) =>
              setSelected((v) => {
                const n = new Set(v);
                e.target.checked ? n.add(c.id) : n.delete(c.id);
                return n;
              })
            }
          />
          <span>
            Vol. {c.volume || "—"} · Cap. {c.number} {c.title} · {c.language}
          </span>
          <button onClick={() => open(c)}>Ler</button>
          <button onClick={() => download([c])}>Baixar CBZ</button>
        </div>
      ))}
    </>
  );
}
function Reader({
  route,
  report,
}: {
  route: Route;
  report: (e: unknown) => void;
}) {
  const [pages, setPages] = useState<string[]>(route.pages || []),
    [page, setPage] = useState(route.page || 0);
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!route.chapter) return;
    const id = op();
    api.Pages(id, route.chapter.id).then(setPages).catch(report);
    return () => {
      api.Cancel(id);
    };
  }, []);
  useEffect(() => {
    if (!pages.length) return;
    const el = container.current?.querySelector(
      `[data-page="${route.page || 0}"]`,
    );
    el?.scrollIntoView();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting)
            setPage(Number((e.target as HTMLElement).dataset.page));
        }
      },
      { threshold: 0.25 },
    );
    container.current
      ?.querySelectorAll("[data-page]")
      .forEach((e) => observer.observe(e));
    return () => observer.disconnect();
  }, [pages]);
  useEffect(() => {
    if (!route.manga || !route.chapter) return;
    const t = setTimeout(
      () =>
        api
          .SaveMangaProgress({
            manga: route.manga!,
            chapter: route.chapter!,
            page,
            updated: 0,
          })
          .catch(report),
      500,
    );
    return () => clearTimeout(t);
  }, [page]);
  return (
    <div className="reader" ref={container}>
      <div className="reader-tools">
        Página {page + 1} / {pages.length || "…"}{" "}
        <select
          aria-label="Ir à página"
          value={page}
          onChange={(e) =>
            container.current
              ?.querySelector(`[data-page="${e.target.value}"]`)
              ?.scrollIntoView()
          }
        >
          {pages.map((_, i) => (
            <option key={i} value={i}>
              {i + 1}
            </option>
          ))}
        </select>
      </div>
      {!pages.length && <Busy />}
      {pages.map((url, i) => (
        <div key={url} data-page={i} className="manga-page">
          <img
            src={url}
            alt={`Página ${i + 1}`}
            loading={
              i < 2 || Math.abs(i - (route.page || 0)) < 2 ? "eager" : "lazy"
            }
            onError={(e) => {
              e.currentTarget.alt = `Página ${i + 1} indisponível. Reabra o capítulo para atualizar as URLs.`;
            }}
          />
        </div>
      ))}
    </div>
  );
}
function AccountsView({ report }: { report: (e: unknown) => void }) {
  const [accounts, setAccounts] = useState<Account[]>([]),
    [busy, setBusy] = useState("");
  const load = () => api.Accounts().then(setAccounts).catch(report);
  useEffect(() => {
    load();
    const t = setInterval(() => {
      api
        .Accounts()
        .then((xs) =>
          xs
            .filter((x) => x.connected)
            .forEach((x) =>
              api.RefreshAccount(op(), x.provider).then(load).catch(report),
            ),
        );
    }, 300000);
    return () => clearInterval(t);
  }, []);
  const login = async (p: string) => {
    setBusy(p);
    try {
      await api.Login("login", p);
      await load();
    } catch (e) {
      report(e);
    } finally {
      setBusy("");
    }
  };
  return (
    <>
      {accounts.map((a) => (
        <article className="account" key={a.provider}>
          <h3>{a.provider === "mal" ? "MyAnimeList" : "AniList"}</h3>
          {a.avatar && <Image src={a.avatar} alt="" />}
          {a.connected ? (
            <>
              <h4>{a.name || "Conta conectada"}</h4>
              <p>
                {a.animeCount} animes · {a.episodes} episódios ·{" "}
                {Math.round(a.minutes / 60)} horas
              </p>
              <button
                onClick={() =>
                  api.RefreshAccount(op(), a.provider).then(load).catch(report)
                }
              >
                Atualizar perfil
              </button>
              <button
                onClick={() => api.Logout(a.provider).then(load).catch(report)}
              >
                Sair da conta
              </button>
            </>
          ) : (
            <button disabled={!!busy} onClick={() => login(a.provider)}>
              Entrar pelo navegador
            </button>
          )}
        </article>
      ))}
      {busy && <Busy cancel={() => api.Cancel("login")} />}
      <p>
        O login abre o navegador do sistema. Autorize o AnimeCaos e aguarde o
        retorno ao aplicativo.
      </p>
    </>
  );
}
function SettingsView({
  settings,
  save,
  report,
  navigate,
}: {
  settings: Settings;
  save: (s: Settings) => Promise<void>;
  report: (e: unknown) => void;
  navigate: (name: string) => void;
}) {
  const [v, setV] = useState(settings),
    [saved, setSaved] = useState(false),
    [update, setUpdate] = useState<Update>(),
    [packagePath, setPackage] = useState("");
  const patch = (x: Partial<Settings>) => {
    setV({ ...v, ...x });
    setSaved(false);
  };
  return (
    <form
      className="settings"
      onSubmit={(e) => {
        e.preventDefault();
        save(v)
          .then(() => setSaved(true))
          .catch(report);
      }}
    >
      <label>
        Aparência
        <select value={v.theme || "system"} onChange={(e) => patch({ theme: e.target.value as Settings["theme"] })}>
          <option value="system">Usar preferência do sistema</option>
          <option value="light">Claro</option>
          <option value="dark">Escuro</option>
        </select>
      </label>
      <label>
        Escala da interface{" "}
        <input
          type="range"
          min="1"
          max="1.5"
          step="0.05"
          value={v.uiScale}
          onChange={(e) => patch({ uiScale: +e.target.value })}
        />{" "}
        {Math.round(v.uiScale * 100)}%
      </label>
      <label>
        Player
        <select
          value={v.playerMode}
          onChange={(e) => patch({ playerMode: e.target.value })}
        >
          <option value="mpv">MPV integrado</option>
          <option value="system">Player padrão do sistema</option>
          <option value="custom">Player personalizado</option>
        </select>
      </label>
      {v.playerMode === "custom" && (
        <label>
          Executável{" "}
          <input
            value={v.playerPath}
            onChange={(e) => patch({ playerPath: e.target.value })}
          />
          <button
            type="button"
            onClick={() =>
              desktop()
                .ChoosePlayer()
                .then((p) => p && patch({ playerPath: p }))
                .catch(report)
            }
          >
            Escolher
          </button>
        </label>
      )}
      {v.playerMode !== "mpv" && (
        <p>Controles no app e autoplay requerem MPV.</p>
      )}
      <label>
        Pasta de downloads
        <input
          value={v.downloadsDir}
          onChange={(e) => patch({ downloadsDir: e.target.value })}
        />
        <button
          type="button"
          onClick={() =>
            desktop()
              .ChooseDirectory()
              .then((p) => p && patch({ downloadsDir: p }))
              .catch(report)
          }
        >
          Escolher pasta
        </button>
      </label>
      <label>
        Downloads simultâneos
        <input
          type="number"
          min="1"
          max="5"
          value={v.concurrent}
          onChange={(e) => patch({ concurrent: +e.target.value })}
        />
      </label>
      <label>
        Áudio preferido
        <select
          value={v.audio}
          onChange={(e) => patch({ audio: e.target.value })}
        >
          <option value="legendado">Legendado</option>
          <option value="dublado">Dublado</option>
        </select>
      </label>
      <label>
        <input
          type="checkbox"
          checked={v.autoplay}
          onChange={(e) => patch({ autoplay: e.target.checked })}
        />
        Reproduzir próximo episódio automaticamente
      </label>
      <label>
        <input
          type="checkbox"
          checked={v.discord}
          onChange={(e) => patch({ discord: e.target.checked })}
        />
        Discord Rich Presence
      </label>
      <label>
        <input
          type="checkbox"
          checked={v.autoClose}
          onChange={(e) => patch({ autoClose: e.target.checked })}
        />
        Fechar painel ao terminar os downloads
      </label>
      <label>
        Espera para fechar (ms)
        <input
          type="number"
          min="0"
          max="60000"
          value={v.autoCloseMs}
          onChange={(e) => patch({ autoCloseMs: +e.target.value })}
        />
      </label>
      <label>
        MyAnimeList Client ID
        <input
          value={v.malClientId}
          onChange={(e) => patch({ malClientId: e.target.value })}
        />
      </label>
      <button type="submit">Salvar configurações</button>
      {saved && <p role="status">Configurações salvas.</p>}
      <div className="settings-links"><span>Mais opções</span><button type="button" onClick={() => navigate("accounts")}>Contas conectadas</button><button type="button" onClick={() => navigate("logs")}>Diagnóstico</button></div>
      <hr />
      <button
        type="button"
        onClick={() =>
          api
            .ClearCache()
            .then(() => setSaved(true))
            .catch(report)
        }
      >
        Limpar cache de metadados
      </button>
      <button
        type="button"
        onClick={() => api.CheckUpdate(op()).then(setUpdate).catch(report)}
      >
        Verificar atualização
      </button>
      {update && (
        <div>
          <p>
            {update.managed
              ? "Atualize pelo Flatpak."
              : update.available
                ? `Versão ${update.version} disponível.`
                : "Você está na versão mais recente disponível para esta plataforma."}
          </p>
          <pre>{update.notes}</pre>
          {update.available && !update.managed && (
            <button
              type="button"
              onClick={() =>
                api.DownloadUpdate(op(), update).then(setPackage).catch(report)
              }
            >
              Baixar e verificar pacote
            </button>
          )}
          {packagePath && (
            <div>
              <p>Pacote verificado: {packagePath}</p>
              <button
                type="button"
                onClick={() => api.InstallUpdate(packagePath).catch(report)}
              >
                Instalar e reiniciar
              </button>
            </div>
          )}
        </div>
      )}
    </form>
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
