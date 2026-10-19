import type {
  Anime,
  Episode,
  Detail,
  SearchResult,
  History,
  Settings,
  Download,
  LocalFile,
  Account,
  Manga,
  Chapter,
  MangaProgress,
  Update,
} from "./types";
export interface API {
  Image(source: string): Promise<string>;
  InstallUpdate(path: string): Promise<void>;
  Diagnose(): Promise<unknown>;
  OfflinePages(path: string): Promise<string[]>;
  Initial(): Promise<{
    settings: Settings;
    version: string;
    accounts: Account[];
  }>;
  Cancel(id: string): Promise<void>;
  Search(id: string, q: string, page: number, preferred?: Anime | null): Promise<SearchResult>;
  Discover(
    id: string,
  ): Promise<{ trending: Anime[]; seasonal: Anime[]; warning: string }>;
  Details(id: string, a: Anime): Promise<Detail>;
  Preview(id: string, title: string, preferredAniListID: number): Promise<Anime>;
  Library(): Promise<Anime[]>;
  Favorite(a: Anime, enabled: boolean): Promise<void>;
  History(): Promise<History[]>;
  SaveHistoryCover(key: string, cover: string): Promise<void>;
  RemoveHistory(key: string): Promise<void>;
  Resume(id: string, key: string): Promise<void>;
  Play(
    id: string,
    a: Anime,
    episodes: Episode[],
    index: number,
    resume: boolean,
  ): Promise<void>;
  PlayerCommand(name: string, value: number): Promise<void>;
  Adjacent(delta: number): Promise<void>;
  Enqueue(a: Anime, episodes: Episode[]): Promise<Download[]>;
  Downloads(): Promise<Download[]>;
  CancelDownload(id: string): Promise<void>;
  LocalFiles(): Promise<LocalFile[]>;
  DeleteFile(path: string): Promise<void>;
  PlayLocal(path: string): Promise<void>;
  OpenDownloads(): Promise<void>;
  OpenLocalFolder(path: string): Promise<void>;
  MangaSearch(id: string, q: string): Promise<Manga[]>;
  Chapters(id: string, mangaId: string): Promise<Chapter[]>;
  ChaptersLanguage(id: string, mangaId: string, language: string): Promise<Chapter[]>;
  Pages(id: string, chapterId: string): Promise<string[]>;
  MangaHistory(): Promise<MangaProgress[]>;
  SaveMangaProgress(p: MangaProgress): Promise<void>;
  DownloadManga(id: string, m: Manga, ch: Chapter[]): Promise<void>;
  Accounts(): Promise<Account[]>;
  MALClientSecretConfigured(): Promise<boolean>;
  SetMALClientSecret(secret: string): Promise<void>;
  Login(id: string, provider: string): Promise<void>;
  Logout(provider: string): Promise<void>;
  RefreshAccount(id: string, provider: string): Promise<Account>;
  SaveSettings(v: Settings): Promise<void>;
  ClearCache(): Promise<void>;
  CheckUpdate(id: string): Promise<Update>;
  DownloadUpdate(id: string, info: Update): Promise<string>;
}
declare global {
  interface Window {
    go: {
      app: { Service: API };
      main: {
        Desktop: {
          ChooseDirectory(): Promise<string>;
          ChoosePlayer(): Promise<string>;
          OpenLink(url: string): Promise<void>;
        };
      };
    };
    runtime: {
      EventsOn(name: string, callback: (data: any) => void): () => void;
    };
  }
}
export const api: API = new Proxy({} as API, {
  get:
    (_, name) =>
    (...args: unknown[]) => {
      const method = window.go?.app?.Service?.[name as keyof API];
      if (!method)
        return Promise.reject(
          new Error("Abra esta interface pelo aplicativo AnimeCaos (Wails)."),
        );
      return (method as (...a: unknown[]) => unknown)(...args);
    },
});
export const desktop = () => window.go.main.Desktop;
export function on<T>(name: string, callback: (data: T) => void) {
  return window.runtime?.EventsOn(name, callback) || (() => {});
}
export const op = () => crypto.randomUUID();
