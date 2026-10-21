// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { api } from "./api";
import type { Anime, Settings, SearchResult, History, Download, LocalFile, Manga, MangaProgress, Chapter, Account } from "./types";
const events = vi.hoisted(() => new Map<string, (data: unknown) => void>());
vi.mock("./api", () => ({
  api: {
    Initial: vi.fn(),
    Library: vi.fn(),
    Downloads: vi.fn(),
    LocalFiles: vi.fn(),
    OpenLocalFolder: vi.fn(),
    PlayLocal: vi.fn(),
    DeleteFile: vi.fn(),
    Discover: vi.fn(),
    Search: vi.fn(),
    Preview: vi.fn(),
    Cancel: vi.fn(),
    Image: vi.fn(),
    MangaSearch: vi.fn(),
    MangaDiscover: vi.fn(),
    MangaByCategory: vi.fn(),
    Chapters: vi.fn(),
    ChaptersLanguage: vi.fn(),
    Pages: vi.fn(),
    MangaHistory: vi.fn(),
    SaveMangaProgress: vi.fn(),
    DownloadManga: vi.fn(),
    Accounts: vi.fn(),
    Login: vi.fn(),
    Logout: vi.fn(),
    RefreshAccount: vi.fn(),
    History: vi.fn(),
    SaveHistoryCover: vi.fn(),
    Resume: vi.fn(),
    SaveSettings: vi.fn(),
    ClearCache: vi.fn(),
  },
  desktop: () => ({ OpenLink: vi.fn() }),
  op: () => crypto.randomUUID(),
  on: (name: string, cb: (data: unknown) => void) => {
    events.set(name, cb);
    return () => events.delete(name);
  },
}));
const settings: Settings = {
  uiScale: 1,
  theme: "system",
  playerMode: "mpv",
  playerPath: "",
  downloadsDir: "D:\\Downloads",
  concurrent: 2,
  autoClose: false,
  autoCloseMs: 3000,
  autoplay: true,
  audio: "legendado",
  discord: false,
  width: 1280,
  height: 820,
  x: 0,
  y: 0,
};
beforeEach(() => {
  vi.resetAllMocks();
  events.clear();
  localStorage.removeItem("animecaos-sidebar-collapsed");
  vi.mocked(api.Initial).mockResolvedValue({
    settings,
    version: "test",
    accounts: [],
  });
  vi.mocked(api.Library).mockResolvedValue([]);
  vi.mocked(api.Downloads).mockResolvedValue([]);
  vi.mocked(api.LocalFiles).mockResolvedValue([]);
  vi.mocked(api.History).mockResolvedValue([]);
  vi.mocked(api.Preview).mockResolvedValue({} as Anime);
  vi.mocked(api.Resume).mockResolvedValue();
  vi.mocked(api.SaveSettings).mockResolvedValue();
  vi.mocked(api.ClearCache).mockResolvedValue();
  vi.mocked(api.Accounts).mockResolvedValue([]);
  vi.mocked(api.Login).mockResolvedValue();
  vi.mocked(api.Logout).mockResolvedValue();
  vi.mocked(api.RefreshAccount).mockResolvedValue({ provider: "anilist", connected: true, id: 1, name: "Conta", avatar: "", animeCount: 0, episodes: 0, minutes: 0, error: "" });
  vi.mocked(api.OpenLocalFolder).mockResolvedValue();
  vi.mocked(api.PlayLocal).mockResolvedValue();
  vi.mocked(api.DeleteFile).mockResolvedValue();
  vi.mocked(api.Discover).mockResolvedValue({
    trending: [],
    seasonal: [],
    warning: "",
  });
  vi.mocked(api.Cancel).mockResolvedValue();
  vi.mocked(api.Image).mockResolvedValue("");
  vi.mocked(api.MangaSearch).mockResolvedValue([]);
  vi.mocked(api.MangaDiscover).mockResolvedValue({ featured: [], popular: [], recentlyUpdated: [], publishing: [], categories: [], warning: "" });
  vi.mocked(api.MangaByCategory).mockResolvedValue([]);
  vi.mocked(api.Chapters).mockResolvedValue([]);
  vi.mocked(api.ChaptersLanguage).mockResolvedValue([]);
  vi.mocked(api.Pages).mockResolvedValue([]);
  vi.mocked(api.MangaHistory).mockResolvedValue([]);
  vi.mocked(api.SaveMangaProgress).mockResolvedValue();
  vi.mocked(api.DownloadManga).mockResolvedValue();
  globalThis.IntersectionObserver = class {
    observe() {}
    disconnect() {}
    unobserve() {}
  } as unknown as typeof IntersectionObserver;
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(cleanup);
async function renderReadyApp() {
  const originalSetTimeout = window.setTimeout;
  const expediteStartupTimers: typeof window.setTimeout = (handler, timeout, ...args) =>
    originalSetTimeout(handler, Math.min(timeout ?? 0, 1), ...args);
  window.setTimeout = expediteStartupTimers;
  try {
    const rendered = render(<App />);
    rendered.container.querySelectorAll<HTMLImageElement>(".startup-splash img").forEach((image) => fireEvent.load(image));
    rendered.container.querySelectorAll<HTMLVideoElement>(".startup-splash video").forEach((video) => fireEvent.loadedData(video));
    await act(async () => {
      await new Promise<void>((resolve) => originalSetTimeout(resolve, 20));
    });
    return rendered;
  } finally {
    window.setTimeout = originalSetTimeout;
  }
}
describe("splash de inicialização", () => {
  it("sincroniza o fade da wordmark com o primeiro quadro pronto do vídeo", () => {
    const { container } = render(<App />);
    const wordmark = container.querySelector<HTMLImageElement>(".startup-splash-wordmark");
    const video = container.querySelector<HTMLVideoElement>(".startup-splash-mascot-video");
    expect(wordmark).toBeTruthy();
    expect(video).toBeTruthy();
    expect(container.querySelector(".startup-splash-mascot-poster")).toBeNull();

    fireEvent.load(wordmark!);
    expect(wordmark!.classList.contains("startup-splash-art-loaded")).toBe(false);
    expect(video!.classList.contains("startup-splash-art-loaded")).toBe(false);

    fireEvent.loadedData(video!);
    expect(wordmark!.classList.contains("startup-splash-art-loaded")).toBe(true);
    expect(video!.classList.contains("startup-splash-art-loaded")).toBe(true);
  });

  it("tenta recarregar o vídeo e não revela a logo se a animação falhar", () => {
    const { container } = render(<App />);
    const firstVideo = container.querySelector<HTMLVideoElement>(".startup-splash-mascot-video")!;
    const wordmark = container.querySelector<HTMLImageElement>(".startup-splash-wordmark")!;

    fireEvent.load(wordmark);
    fireEvent.error(firstVideo);

    const retriedVideo = container.querySelector<HTMLVideoElement>(".startup-splash-mascot-video")!;
    expect(retriedVideo.getAttribute("src")).toBe("/avatar_loop.webm?retry=1");
    expect(wordmark.classList.contains("startup-splash-art-loaded")).toBe(false);

    fireEvent.error(retriedVideo);
    expect(screen.getByRole("alert").textContent).toContain("Não foi possível carregar a animação.");
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(container.querySelector(".startup-splash-video-error")).toBeNull();
    expect(container.querySelector<HTMLVideoElement>(".startup-splash-mascot-video")!.getAttribute("src")).toBe("/avatar_loop.webm?retry=2");
  });
});
async function searchScreen() {
  await renderReadyApp();
  const navigation = await screen.findByRole("navigation", { name: "Navegação principal" });
  fireEvent.click(within(navigation).getByRole("button", { name: "Pesquisar" }));
  return screen.getAllByRole("searchbox", { name: "Buscar animes" })[0];
}
describe("interface funcional", () => {
  it("mostra descoberta de mangás no padrão da Home e filtra uma categoria", async () => {
    const popular = { id: "popular-1", title: "One Piece", description: "Aventura no mar", cover: "", banner: "", status: "ongoing", languages: ["pt-br"] } as Manga;
    const result = { id: "genre-1", title: "Dandadan", description: "Mistério e ação", cover: "", status: "ongoing", languages: ["pt-br"] } as Manga;
    vi.mocked(api.MangaDiscover).mockResolvedValue({
      featured: [popular], popular: [popular], recentlyUpdated: [], publishing: [],
      categories: [{ id: "genre-id", name: "Ação" }], warning: "",
    });
    vi.mocked(api.MangaHistory).mockResolvedValue([{
      manga: popular,
      chapter: { id: "chapter-12", title: "", number: "12", volume: "", language: "pt-br", pages: 40 },
      page: 16,
      updated: 10,
    } as MangaProgress]);
    vi.mocked(api.MangaByCategory).mockResolvedValue([result]);
    const { container } = await renderReadyApp();
    const navigation = await screen.findByRole("navigation", { name: "Navegação principal" });
    fireEvent.click(within(navigation).getByRole("button", { name: "Mangás" }));
    expect(await screen.findByRole("heading", { name: "Top mangás" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Categorias" })).toBeTruthy();
    expect(container.querySelector(".manga-library > .spotlight")).toBeTruthy();
    expect(screen.getAllByRole("searchbox", { name: "Buscar mangás" })).toHaveLength(1);
    expect(container.querySelector(".manga-category-list")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Ação" }).classList.contains("manga-category-chip")).toBe(true);
    expect(container.querySelector(".manga-history-card.card .card-poster")).toBeTruthy();
    expect(screen.queryByText("As obras mais acompanhadas no catálogo.")).toBeNull();
    expect(screen.queryByText("Escolha um gênero e encontre sua próxima leitura.")).toBeNull();
    const mangaCard = container.querySelector(".manga-shelf-card") as HTMLButtonElement;
    fireEvent.mouseEnter(mangaCard);
    const mangaPreview = await screen.findByRole("tooltip");
    expect(mangaPreview.textContent).toContain("One Piece");
    expect(mangaPreview.textContent).toContain("Aventura no mar");
    expect(mangaCard.getAttribute("aria-describedby")).toBe(mangaPreview.id);
    expect(api.Preview).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Ação" }));
    expect(await screen.findByRole("heading", { name: "Ação" })).toBeTruthy();
    expect(await screen.findByRole("button", { name: /Dandadan/ })).toBeTruthy();
    expect(api.MangaByCategory).toHaveBeenCalledWith(expect.any(String), "genre-id");
  });

  it("pesquisa, abre capítulos, lê páginas e salva o progresso do mangá", async () => {
    const manga = { id: "manga-1", title: "One Piece", description: "A tripulação parte em uma aventura.", cover: "", status: "ongoing", languages: ["pt-br"] } as Manga;
    const chapter = { id: "chapter-1", title: "Romance Dawn", number: "1", volume: "1", language: "pt-br", pages: 2 } as Chapter;
    vi.mocked(api.MangaSearch).mockResolvedValue([manga]);
    vi.mocked(api.Chapters).mockResolvedValue([chapter]);
    vi.mocked(api.Pages).mockResolvedValue(["http://127.0.0.1/page-1", "http://127.0.0.1/page-2"]);
    await renderReadyApp();
    const navigation = await screen.findByRole("navigation", { name: "Navegação principal" });
    fireEvent.click(within(navigation).getByRole("button", { name: "Mangás" }));
    expect(await screen.findByRole("heading", { name: "Sua próxima história começa aqui" })).toBeTruthy();
    const headerSearch = screen.getByRole("searchbox", { name: "Buscar mangás" });
    expect(headerSearch.getAttribute("placeholder")).toBe("Buscar mangás...");
    expect(screen.queryByRole("searchbox", { name: "Buscar animes" })).toBeNull();
    expect(api.MangaSearch).not.toHaveBeenCalled();
    fireEvent.change(headerSearch, { target: { value: "One Piece" } });
    fireEvent.submit(headerSearch.closest("form")!);
    const result = await screen.findByRole("button", { name: /One Piece/ });
    expect(api.MangaSearch).toHaveBeenCalledWith(expect.any(String), "One Piece");
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("searchbox", { name: "Buscar mangás" })));
    expect(screen.getByRole("heading", { name: "Sua próxima história começa aqui" })).toBeTruthy();
    fireEvent.click(result);
    expect(await screen.findByRole("heading", { name: "Capítulos" })).toBeTruthy();
    expect(screen.getByRole("searchbox", { name: "Buscar mangás" })).toBeTruthy();
    expect(screen.queryByRole("searchbox", { name: "Buscar animes" })).toBeNull();
    expect(await screen.findByText(/Romance Dawn/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ler capítulo" }));
    expect(await screen.findByAltText("Página 1")).toBeTruthy();
    expect(screen.getByRole("searchbox", { name: "Buscar mangás" })).toBeTruthy();
    expect(screen.queryByRole("searchbox", { name: "Buscar animes" })).toBeNull();
    expect(screen.getByRole("combobox", { name: "Modo de leitura" })).toBeTruthy();
    await waitFor(() => expect(api.SaveMangaProgress).toHaveBeenCalledWith(expect.objectContaining({ manga, chapter, page: 0 })));
  });

  it("mostra falha do capítulo e permite recarregar as páginas", async () => {
    const manga = { id: "manga-retry", title: "Mangá de teste", cover: "", languages: ["pt-br"] } as Manga;
    const chapter = { id: "chapter-retry", title: "Capítulo", number: "1", language: "pt-br", pages: 1 } as Chapter;
    vi.mocked(api.MangaSearch).mockResolvedValue([manga]);
    vi.mocked(api.Chapters).mockResolvedValue([chapter]);
    vi.mocked(api.Pages).mockRejectedValueOnce(new Error("servidor de imagens indisponível")).mockResolvedValue(["http://127.0.0.1/recovered"]);
    await renderReadyApp();
    const navigation = await screen.findByRole("navigation", { name: "Navegação principal" });
    fireEvent.click(within(navigation).getByRole("button", { name: "Mangás" }));
    const searchbox = screen.getByRole("searchbox", { name: "Buscar mangás" });
    fireEvent.change(searchbox, { target: { value: "Mangá de teste" } });
    fireEvent.submit(searchbox.closest("form")!);
    fireEvent.click(await screen.findByRole("button", { name: /Mangá de teste/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Ler capítulo" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(await screen.findByAltText("Página 1")).toBeTruthy();
    expect(api.Pages).toHaveBeenCalledTimes(2);
  });

  it("continua pelo identificador salvo sem escolher episódio por posição", async () => {
    vi.mocked(api.History).mockResolvedValue([{anime:{id:"anime",provider:"animefire",title:"Continuar teste"},episode:{id:"episode",season:2,number:3},position:120,updated:1,needsResolve:false}] as History[]);
    await renderReadyApp();
    const shelfButton = await screen.findByRole("button",{name:"Continuar"});
    expect(shelfButton.querySelector("svg.nav-icon path")?.getAttribute("d")).toBe("m8 5 11 7-11 7V5Z");
    fireEvent.click(await screen.findByRole("button",{name:"Histórico"}));
    const continueButton = await screen.findByRole("button",{name:"Continuar"});
    expect(continueButton.querySelector("svg.nav-icon path")?.getAttribute("d")).toBe("m8 5 11 7-11 7V5Z");
    fireEvent.click(continueButton);
    await waitFor(()=>expect(api.Resume).toHaveBeenCalledWith(expect.any(String),"animefire:anime"));
  });
  it("exige escolher o episódio quando o histórico antigo não tem identidade segura", async () => {
    vi.mocked(api.History).mockResolvedValue([{anime:{id:"old",provider:"legacy",title:"Legado"},episode:{},position:0,updated:0,needsResolve:true}] as History[]);
    await renderReadyApp();
    await screen.findByText("Histórico antigo");
    expect(screen.queryByRole("button",{name:"Escolher episódio"})).toBeNull();
    expect(screen.queryByRole("button",{name:"Continuar"})).toBeNull();
    expect(api.Resume).not.toHaveBeenCalled();
  });
  it("recupera a capa dos itens antigos do histórico", async () => {
    vi.mocked(api.History).mockResolvedValue([{anime:{id:"old-cover",provider:"legacy",title:"Bleach"},episode:{},position:0,updated:0,needsResolve:true}] as History[]);
    vi.mocked(api.Preview).mockResolvedValue({ cover: "https://images.example/bleach.jpg" } as Anime);
    const { container } = await renderReadyApp();
    await waitFor(() => expect(api.Preview).toHaveBeenCalledWith(expect.any(String), "Bleach", 0));
    await waitFor(() => expect(container.querySelector(".continue-shelf .card img")).toBeTruthy());
    await waitFor(() => expect(api.SaveHistoryCover).toHaveBeenCalledWith("legacy:old-cover", "https://images.example/bleach.jpg"));
  });
  it("substitui e salva uma capa antiga cujo endereço falhou", async () => {
    vi.mocked(api.History).mockResolvedValue([{anime:{id:"stale-cover",provider:"legacy",title:"Anime legado",cover:"https://images.example/broken.jpg"},episode:{},position:0,updated:0,needsResolve:true}] as History[]);
    vi.mocked(api.Preview).mockResolvedValue({ cover: "https://images.example/recovered.jpg" } as Anime);
    vi.mocked(api.Image).mockRejectedValue(new Error("imagem antiga indisponível"));
    globalThis.IntersectionObserver = class {
      constructor(private callback: IntersectionObserverCallback) {}
      observe(target: Element) { this.callback([{ isIntersecting: true, target } as IntersectionObserverEntry], this as unknown as IntersectionObserver); }
      disconnect() {}
    } as unknown as typeof IntersectionObserver;
    await renderReadyApp();
    await waitFor(() => expect(api.Preview).toHaveBeenCalledWith(expect.any(String), "Anime legado", 0));
    await waitFor(() => expect(api.SaveHistoryCover).toHaveBeenCalledWith("legacy:stale-cover", "https://images.example/recovered.jpg"));
  });
  it("mostra o histórico como uma estante de capas com ações compactas", async () => {
    vi.mocked(api.History).mockResolvedValue([{anime:{id:"old-history",provider:"legacy",title:"Bleach: Temporada longa"},episode:{},position:0,updated:10,needsResolve:true}] as History[]);
    await renderReadyApp();
    fireEvent.click(await screen.findByRole("button", { name: "Histórico" }));
    expect(await screen.findByRole("region", { name: "Histórico de animes" })).toBeTruthy();
    expect(screen.getByText("Assistidos recentemente")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Encontrar episódios" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Escolher episódio" })).toBeNull();
    expect(document.querySelector(".history-grid .history-poster")).toBeTruthy();
    expect(document.querySelector(".history-page .row")).toBeNull();
  });
  it("pagina o histórico em blocos de 24 e mantém a ordem mais recente", async () => {
    const history = Array.from({ length: 25 }, (_, index) => ({
      anime: { id: `history-${index}`, provider: "animefire", title: `Anime ${index + 1}`, cover: "cover" },
      episode: { season: 1, number: index + 1 },
      position: 0,
      updated: index,
      needsResolve: true,
    })) as History[];
    vi.mocked(api.History).mockResolvedValue(history);
    await renderReadyApp();
    fireEvent.click(await screen.findByRole("button", { name: "Histórico" }));
    const cards = await screen.findAllByRole("button", { name: /^Abrir Anime/ });
    expect(cards).toHaveLength(24);
    expect(screen.getAllByText("Mostrando 1–24 de 25")).toHaveLength(2);
    fireEvent.click(screen.getAllByRole("button", { name: "Próxima página" })[0]);
    await waitFor(() => expect(screen.getByRole("button", { name: "Abrir Anime 1" })).toBeTruthy());
    expect(screen.getAllByRole("button", { name: /^Abrir Anime/ })).toHaveLength(1);
    expect(screen.getAllByText("Mostrando 25–25 de 25")).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "Página anterior" }).every((button) => !button.hasAttribute("disabled"))).toBe(true);
  });
  it("recolhe a sidebar e mantém acessível a ação para expandi-la", async () => {
    const { container } = await renderReadyApp();
    await screen.findAllByRole("button", { name: "Recolher menu" });
    const toggle = container.querySelector(".brand .sidebar-toggle") as HTMLButtonElement;
    fireEvent.click(toggle);
    expect(container.querySelector(".app")?.classList.contains("sidebar-collapsed")).toBe(true);
    expect(container.querySelector('.brand .sidebar-toggle[aria-label="Expandir menu"]')).toBeTruthy();
    expect(localStorage.getItem("animecaos-sidebar-collapsed")).toBe("true");
  });
  it("leva a pesquisa da navegação e do atalho ao campo único da home", async () => {
    await renderReadyApp();
    const navigation = await screen.findByRole("navigation", { name: "Navegação principal" });
    fireEvent.click(within(navigation).getByRole("button", { name: "Pesquisar" }));
    expect(screen.getByRole("heading", { name: "Início" })).toBeTruthy();
    expect(screen.getAllByRole("searchbox")).toHaveLength(1);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("searchbox", { name: "Buscar animes" })));
    fireEvent.keyDown(window, { key: "f", ctrlKey: true });
    expect(document.activeElement).toBe(screen.getByRole("searchbox", { name: "Buscar animes" }));
  });
  it("envia a busca pelo campo compacto do cabeçalho", async () => {
    vi.mocked(api.Search).mockResolvedValue({ items: [], page: 1, hasNext: false, warnings: [] });
  vi.mocked(api.Preview).mockResolvedValue({} as Anime);
    await renderReadyApp();
    const input = await screen.findByRole("searchbox", { name: "Buscar animes" });
    fireEvent.change(input, { target: { value: "Frieren" } });
    fireEvent.submit(input.closest("form")!);
    await waitFor(() => expect(api.Search).toHaveBeenCalledWith(expect.any(String), "Frieren", 1, undefined));
  });
  it("ao selecionar um destaque da home, pesquisa pelo título canônico", async () => {
    const featured = { id: "anilist:101", provider: "anilist", title: "Demon Slayer", anilistId: 101, titles: ["Kimetsu no Yaiba"] } as Anime;
    vi.mocked(api.Discover).mockResolvedValue({ trending: [featured], seasonal: [], warning: "" });
    vi.mocked(api.Search).mockResolvedValue({ items: [], page: 1, hasNext: false, warnings: [] });
    await renderReadyApp();
    fireEvent.click(await screen.findByRole("button", { name: "Assistir" }));
    await waitFor(() => expect(api.Search).toHaveBeenCalledWith(expect.any(String), "Demon Slayer", 1, featured));
  });
  it("mostra Ver anime nas capas das prateleiras da Home e mantém a ação do card", async () => {
    const trending = { id: "anime-trending", provider: "anilist", title: "Demon Slayer", anilistId: 101 } as Anime;
    const seasonal = { id: "anime-seasonal", provider: "anilist", title: "Frieren" } as Anime;
    vi.mocked(api.Discover).mockResolvedValue({ trending: [trending], seasonal: [seasonal], warning: "" });
    vi.mocked(api.History).mockResolvedValue([{
      anime: { id: "anime-history", provider: "anilist", title: "Mob Psycho 100" },
      episode: { id: "episode-1", season: 1, number: 1 },
      position: 30,
      updated: 10,
      needsResolve: false,
    } as History]);
    vi.mocked(api.Search).mockResolvedValue({ items: [], page: 1, hasNext: false, warnings: [] });
    await renderReadyApp();

    await waitFor(() => expect(screen.getAllByText("Ver anime", { exact: true })).toHaveLength(3));
    const labels = screen.getAllByText("Ver anime", { exact: true });
    fireEvent.click(labels[1]);
    await waitFor(() => expect(api.Search).toHaveBeenCalledWith(expect.any(String), "Demon Slayer", 1, trending));
  });
  it("navega os destaques com as setas do teclado", async () => {
    const first = { id: "a", provider: "anilist", title: "Anime A" } as Anime;
    const second = { id: "b", provider: "anilist", title: "Anime B" } as Anime;
    vi.mocked(api.Discover).mockResolvedValue({ trending: [first, second], seasonal: [], warning: "" });
    await renderReadyApp();
    const hero = await screen.findByRole("button", { name: "Assistir" });
    fireEvent.keyDown(hero, { key: "ArrowRight" });
    expect(screen.getByRole("button", { name: "Destaque 2: Anime B" }).getAttribute("aria-pressed")).toBe("true");
  });
  it("renderiza a prévia acima dos carrosséis em uma camada de viewport", async () => {
    const featured = { id: "anime-1", provider: "anilist", title: "Frieren" } as Anime;
    vi.mocked(api.Discover).mockResolvedValue({ trending: [featured], seasonal: [], warning: "" });
    vi.mocked(api.Preview).mockResolvedValue({ title: "Frieren", description: "Resumo" } as Anime);
    await renderReadyApp();
    await screen.findByText("Frieren", { selector: ".card-title" });
    const card = document.querySelector(".card > button") as HTMLButtonElement;
    fireEvent.mouseEnter(card.closest("article")!);
    const preview = await screen.findByRole("tooltip");
    expect(preview.parentElement).toBe(document.body);
    expect((preview as HTMLElement).style.position).toBe("fixed");
    expect(preview.textContent).toContain("Resumo");
  });
  it("abre os downloads em cards com progresso e ação para o anime", async () => {
    vi.mocked(api.Downloads).mockResolvedValue([{
      id: "job-1",
      anime: { id: "anime-1", provider: "animefire", title: "Frieren", cover: "" },
      episode: { id: "ep-1", season: 2, number: 4, title: "A jornada", audio: "Dublado" },
      status: "downloading", percent: 42, speed: "2 MB/s", eta: "00:30", error: "", path: "", kind: "anime",
    }] as Download[]);
    await renderReadyApp();
    fireEvent.click(await screen.findByRole("button", { name: "Downloads, 1 ativos" }));
    expect(await screen.findByText("Frieren")).toBeTruthy();
    expect(screen.getByText("Temporada 2 · Episódio 4 · Dublado")).toBeTruthy();
    expect(screen.getByText("42%")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Abrir anime" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Fechar downloads" })).toBeTruthy();
  });
  it("mostra ações de ícone acessíveis para arquivos offline e abre a pasta do arquivo", async () => {
    const file = { path: "D:\\Downloads\\Frieren\\Frieren - S01E1-JP.mkv", title: "Frieren", episode: 1, size: 1024, cover: "", kind: "anime" } as LocalFile;
    vi.mocked(api.LocalFiles).mockResolvedValue([file]);
    await renderReadyApp();
    const navigation = await screen.findByRole("navigation", { name: "Navegação principal" });
    fireEvent.click(within(navigation).getByRole("button", { name: "Downloads" }));
    expect(await screen.findByRole("heading", { name: "Disponíveis offline" })).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Abrir pasta de Frieren" }));
    await waitFor(() => expect(api.OpenLocalFolder).toHaveBeenCalledWith(file.path));
    expect(screen.getByRole("button", { name: "Reproduzir Frieren" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Excluir Frieren" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Reproduzir" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Excluir" })).toBeNull();
  });
  it("não exibe identificação das fontes na navegação nem nos cards", async () => {
    const result = {
      id: "1",
      provider: "animefire",
      title: "Resultado",
      titles: [],
      variants: [],
      url: "",
      cover: "",
      banner: "",
      description: "",
      audio: "",
      status: "",
      score: 0,
      year: 0,
      format: "",
      episodeCount: 0,
      anilistId: 0,
      malId: 0,
      season: 0,
    } satisfies Anime;
    vi.mocked(api.Search).mockResolvedValue({ items: [result], page: 1, hasNext: false, warnings: [] });
    const input = await searchScreen();
    fireEvent.change(input, { target: { value: "Resultado" } });
    fireEvent.submit(input.closest("form")!);
    await screen.findByText("Resultado");
    expect(document.body.textContent).not.toMatch(/AnimeFire|AnimesOnlineCC|BetterAnime/);
  });
  it("mostra skeletons discretos e permite cancelar a busca", async () => {
    let finishSearch!: (result: SearchResult) => void;
    vi.mocked(api.Search).mockImplementation(() => new Promise((resolve) => { finishSearch = resolve; }));
    const input = await searchScreen();
    fireEvent.change(input, { target: { value: "Naruto" } });
    fireEvent.submit(input.closest("form")!);
    expect(await screen.findByRole("status", { name: "Buscando animes" })).toBeTruthy();
    expect(document.querySelectorAll(".search-skeleton-grid .skeleton-card")).toHaveLength(10);
    fireEvent.click(screen.getByRole("button", { name: "Cancelar pesquisa" }));
    expect(api.Cancel).toHaveBeenCalledWith(expect.any(String));
    expect(screen.queryByRole("status", { name: "Buscando animes" })).toBeNull();
    await act(async () => finishSearch({ items: [], page: 1, hasNext: false, warnings: [] }));
    expect(screen.queryByRole("status", { name: "Buscando animes" })).toBeNull();
  });
  it("preserva resultados enquanto carrega a próxima página da busca", async () => {
    const first = { id: "first", provider: "animefire", title: "Primeiro resultado" } as Anime;
    const second = { id: "second", provider: "animefire", title: "Segundo resultado" } as Anime;
    let finishMore!: (result: SearchResult) => void;
    vi.mocked(api.Search)
      .mockResolvedValueOnce({ items: [first], page: 1, hasNext: true, warnings: [] })
      .mockImplementationOnce(() => new Promise((resolve) => { finishMore = resolve; }));
    const input = await searchScreen();
    fireEvent.change(input, { target: { value: "Anime" } });
    fireEvent.submit(input.closest("form")!);
    expect(await screen.findByText("Primeiro resultado")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Carregar mais" }));
    expect(screen.getByRole("status", { name: "Carregando mais resultados" })).toBeTruthy();
    expect(screen.getByText("Primeiro resultado")).toBeTruthy();
    expect(document.querySelector(".search-skeleton-grid")).toBeNull();
    await act(async () => finishMore({ items: [second], page: 2, hasNext: false, warnings: [] }));
    expect(await screen.findByText("Segundo resultado")).toBeTruthy();
  });
  it("exibe o lote da busca de uma vez, após receber a qualidade confirmada", async () => {
    const result = {
      id: "verified", provider: "animefire", title: "Verificado", titles: [], variants: [], url: "", cover: "", banner: "", description: "", audio: "", status: "", score: 0, year: 2011, format: "TV", episodeCount: 148, anilistId: 11061, malId: 0, season: 0,
    } satisfies Anime;
    let finishSearch!: (result: SearchResult) => void;
    vi.mocked(api.Search).mockImplementation(() => new Promise((resolve) => { finishSearch = resolve; }));
    const input = await searchScreen();
    fireEvent.change(input, { target: { value: "Verificado" } });
    fireEvent.submit(input.closest("form")!);
    await waitFor(() => expect(api.Search).toHaveBeenCalled());
    expect(screen.queryByText("Verificado")).toBeNull();
    expect(events.get("search-item")).toBeUndefined();
    await act(async () => finishSearch({ items: [{ ...result, availability: { maxHeight: 1080, quality: "Até 1080p", sourcesVerified: ["animefire", "onlinecc"], sampleEpisode: "E1" } }], page: 1, hasNext: false, warnings: [] }));
    expect(await screen.findByText("Verificado")).toBeTruthy();
    expect(screen.getByText("Até 1080p")).toBeTruthy();
    expect(screen.getByText("2011 · 148 eps.")).toBeTruthy();
    expect(document.querySelector(".quality-badge")?.getAttribute("title")).toContain("2 fonte(s) validada(s)");
  });
  it("busca a prévia pelo ID canônico para manter os episódios da adaptação correta", async () => {
    const anime = {
      id: "hunter-2011", provider: "animesonlinecc", title: "Hunter x Hunter", titles: [], variants: [], url: "", cover: "", banner: "", description: "", audio: "", status: "", score: 8.9, year: 2011, format: "TV", episodeCount: 148, anilistId: 11061, malId: 0, season: 0,
    } satisfies Anime;
    vi.mocked(api.Search).mockResolvedValue({ items: [anime], page: 1, hasNext: false, warnings: [] });
    vi.mocked(api.Preview).mockResolvedValue({ title: anime.title, score: 8.9, episodeCount: 148 } as Anime);
    const input = await searchScreen();
    fireEvent.change(input, { target: { value: "hunter" } });
    fireEvent.submit(input.closest("form")!);
    const title = await screen.findByText("Hunter x Hunter", { selector: ".card-title" });
    fireEvent.mouseEnter(title.closest("article")!);
    await waitFor(() => expect(api.Preview).toHaveBeenCalledWith(expect.any(String), "Hunter x Hunter", 11061));
    expect((await screen.findByRole("tooltip")).textContent).toContain("148 episódios");
  });
  it("mostra índice, aplica o tema imediatamente e salva preferências automaticamente", async () => {
    await renderReadyApp();
    await screen.findByRole("navigation", { name: "Navegação principal" });
    const main = await screen.findByRole("main");
    expect(main.closest(".app")?.getAttribute("data-theme")).toBe("system");
    fireEvent.click(await screen.findByRole("button", { name: "Configurações" }));
    expect(screen.getByRole("heading", { name: "Aparência" })).toBeTruthy();
    const settingsIndex = screen.getByRole("navigation", { name: "Índice das configurações" });
    expect(settingsIndex).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Salvar alterações" })).toBeNull();
    expect(api.SaveSettings).not.toHaveBeenCalled();
    fireEvent.click(within(settingsIndex).getByRole("button", { name: "Downloads" }));
    expect(within(settingsIndex).getByRole("button", { name: "Downloads" }).getAttribute("aria-current")).toBe("location");
    fireEvent.click(screen.getByRole("button", { name: "Claro" }));
    expect(main.closest(".app")?.getAttribute("data-theme")).toBe("light");
    expect(screen.getByText("Salvando…").textContent).toBe("Salvando…");
    await waitFor(() => expect(api.SaveSettings).toHaveBeenCalledWith({ ...settings, theme: "light" }));
    expect((await screen.findByText("Salvo")).textContent).toBe("Salvo");
  });
  it("coalesce mudanças rápidas em um salvamento com o estado mais recente", async () => {
    await renderReadyApp();
    fireEvent.click(await screen.findByRole("button", { name: "Configurações" }));
    fireEvent.click(screen.getByRole("button", { name: "Escuro" }));
    fireEvent.change(screen.getByLabelText("Escala da interface"), { target: { value: "1.25" } });
    await waitFor(() => expect(api.SaveSettings).toHaveBeenCalledTimes(1));
    expect(api.SaveSettings).toHaveBeenCalledWith({ ...settings, theme: "dark", uiScale: 1.25 });
    expect(await screen.findByText("125%")).toBeTruthy();
  });
  it("serializa gravações enquanto uma chamada anterior ainda está em andamento", async () => {
    let finishFirst!: () => void;
    vi.mocked(api.SaveSettings).mockImplementationOnce(() => new Promise<void>((resolve) => { finishFirst = resolve; })).mockResolvedValue();
    await renderReadyApp();
    fireEvent.click(await screen.findByRole("button", { name: "Configurações" }));
    fireEvent.click(screen.getByRole("button", { name: "Escuro" }));
    await waitFor(() => expect(api.SaveSettings).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("switch", { name: "Próximo episódio automático" }));
    await act(async () => new Promise((resolve) => window.setTimeout(resolve, 400)));
    expect(api.SaveSettings).toHaveBeenCalledTimes(1);
    await act(async () => finishFirst());
    await waitFor(() => expect(api.SaveSettings).toHaveBeenCalledTimes(2));
    expect(api.SaveSettings).toHaveBeenNthCalledWith(2, { ...settings, theme: "dark", autoplay: false });
  });
  it("preserva uma preferência após falha e permite tentar salvar novamente", async () => {
    vi.mocked(api.SaveSettings).mockRejectedValueOnce(new Error("falha temporária")).mockResolvedValueOnce();
    await renderReadyApp();
    fireEvent.click(await screen.findByRole("button", { name: "Configurações" }));
    fireEvent.click(screen.getByRole("button", { name: "Escuro" }));
    expect(await screen.findByText("Não foi possível salvar.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Escuro" }) as HTMLButtonElement).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    await waitFor(() => expect(api.SaveSettings).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Salvo")).toBeTruthy();
  });
  it("mantém switches acessíveis, mostra campos condicionais e navega para gerenciar contas", async () => {
    const disconnected = [
      { provider: "discord", connected: false, id: 0, name: "", avatar: "", animeCount: 0, episodes: 0, minutes: 0, error: "" },
      { provider: "anilist", connected: false, id: 0, name: "", avatar: "", animeCount: 0, episodes: 0, minutes: 0, error: "" },
      { provider: "mal", connected: false, id: 0, name: "", avatar: "", animeCount: 0, episodes: 0, minutes: 0, error: "" },
    ] satisfies Account[];
    const connected = [
      disconnected[0],
      { ...disconnected[1], connected: true, id: 42, name: "Perfil AniList", animeCount: 12, episodes: 76 },
      disconnected[2],
    ] satisfies Account[];
    vi.mocked(api.Accounts).mockResolvedValueOnce(disconnected).mockResolvedValueOnce(disconnected).mockResolvedValueOnce(connected);
    await renderReadyApp();
    fireEvent.click(await screen.findByRole("button", { name: "Configurações" }));

    await screen.findByText("AniList");
    expect(Array.from(document.querySelectorAll<HTMLImageElement>(".settings-account-summary img")).map((img) => img.getAttribute("src"))).toEqual(["/discord.svg", "/anilist.ico", "/myanimelist.ico"]);
    expect(screen.getByRole("switch", { name: "Discord Rich Presence" })).toBeTruthy();
    expect(screen.getByText(/pelo menos 80%/)).toBeTruthy();
    const autoplay = screen.getByRole("switch", { name: "Próximo episódio automático" }) as HTMLInputElement;
    autoplay.focus();
    await userEvent.keyboard(" ");
    expect(autoplay.checked).toBe(false);
    fireEvent.click(screen.getByRole("switch", { name: "Fechar painel ao concluir" }));
    expect(screen.getByLabelText("Aguardar antes de fechar")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Player"), { target: { value: "custom" } });
    expect(screen.getByLabelText("Executável")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Gerenciar contas" }));
    expect(await screen.findByRole("heading", { name: "Contas conectadas" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Conectar AniList" }));
    await screen.findByText("Perfil AniList");
    expect(api.Login).toHaveBeenCalledWith("login", "anilist");
    expect(screen.getByText(/76 episódios/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Conectar MyAnimeList" }));
    await waitFor(() => expect(api.Login).toHaveBeenLastCalledWith("login", "mal"));
    fireEvent.click(screen.getByRole("button", { name: "Conectar Discord" }));
    await waitFor(() => expect(api.Login).toHaveBeenLastCalledWith("login", "discord"));
  });
  it("oculta domínios das fontes em mensagens comuns", async () => {
    vi.mocked(api.Search).mockRejectedValue(new Error("GET https://api.animefire.one/animes/pesquisar falhou"));
    const input = await searchScreen();
    fireEvent.change(input, { target: { value: "naruto" } });
    fireEvent.submit(input.closest("form")!);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).not.toMatch(/animefire|animesonlinecc|https?:\/\//i);
    expect(alert.textContent).toContain("serviço externo");
  });
  it("encerra o carregamento quando a pesquisa falha", async () => {
    vi.mocked(api.Search).mockRejectedValue(
      new Error("Fonte temporariamente indisponível"),
    );
    const input = await searchScreen();
    fireEvent.change(input, { target: { value: "naruto" } });
    fireEvent.submit(input.closest("form")!);
    await screen.findByRole("alert");
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByRole("alert").textContent).toContain(
      "Fonte temporariamente indisponível",
    );
  });
  it("descarta uma resposta antiga após uma nova busca", async () => {
    let resolveOld!: (r: SearchResult) => void;
    vi.mocked(api.Search)
      .mockImplementationOnce(
        () =>
          new Promise((r) => {
            resolveOld = r;
          }),
      )
      .mockResolvedValueOnce({
        items: [],
        page: 1,
        hasNext: false,
        warnings: [],
      });
    const input = await searchScreen();
    fireEvent.change(input, { target: { value: "antigo" } });
    fireEvent.submit(input.closest("form")!);
    fireEvent.change(input, { target: { value: "atual" } });
    fireEvent.submit(input.closest("form")!);
    await screen.findByText(/Nenhum anime encontrado/);
    await act(async () =>
      resolveOld({
        items: [],
        page: 1,
        hasNext: true,
        warnings: ["RESPOSTA ANTIGA"],
      }),
    );
    expect(screen.queryByText("RESPOSTA ANTIGA")).toBeNull();
    expect(screen.queryByRole("button", { name: "Carregar mais" })).toBeNull();
    expect(api.Cancel).toHaveBeenCalled();
  });
  it("mantém o painel fechado enquanto o download avança", async () => {
    const { container } = await renderReadyApp();
    await screen.findByTitle("Downloads");
    const toggle = container.querySelector<HTMLButtonElement>(".download-toggle")!;
    fireEvent.click(toggle);
    fireEvent.click(screen.getByRole("button", { name: "Fechar downloads" }));
    act(() =>
      events.get("download")?.({
        id: "d1",
        anime: { title: "Teste" },
        episode: { number: 1 },
        status: "downloading",
        percent: 42,
        kind: "anime",
      }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Downloads, 1 ativos" })).toBeTruthy(),
    );
    expect(
      screen.queryByRole("region", { name: "Downloads" }),
    ).toBeNull();
  });
});
