export type Anime = {
  id: string;
  provider: string;
  title: string;
  titles: string[];
  variants?: Anime[];
  url: string;
  cover: string;
  banner: string;
  description: string;
  audio: string;
  status: string;
  score: number;
  year: number;
  format: string;
  episodeCount: number;
  anilistId: number;
  malId: number;
  season: number;
  availability?: {
    maxHeight: number;
    quality: string;
    sourcesVerified: string[];
    sampleEpisode: string;
  };
};
export type Episode = {
  id: string;
  animeId: string;
  provider: string;
  title: string;
  number: number;
  season: number;
  url: string;
  audio: string;
};
export type Detail = { anime: Anime; episodes: Episode[] };
export type SearchResult = {
  items: Anime[];
  page: number;
  hasNext: boolean;
  warnings: string[];
};
export type History = {
  anime: Anime;
  episode: Episode;
  position: number;
  updated: number;
  legacyIndex: number;
  needsResolve: boolean;
};
export type Settings = {
  uiScale: number;
  theme: "system" | "light" | "dark";
  playerMode: string;
  playerPath: string;
  downloadsDir: string;
  concurrent: number;
  autoClose: boolean;
  autoCloseMs: number;
  autoplay: boolean;
  audio: string;
  discord: boolean;
  width: number;
  height: number;
  x: number;
  y: number;
};
export type Download = {
  id: string;
  anime: Anime;
  episode: Episode;
  status: string;
  percent: number;
  speed: string;
  eta: string;
  error: string;
  path: string;
  kind: string;
};
export type LocalFile = {
  path: string;
  title: string;
  episode: number;
  size: number;
  cover: string;
  kind: string;
};
export type Account = {
  provider: string;
  connected: boolean;
  id: number;
  externalId?: string;
  name: string;
  avatar: string;
  animeCount: number;
  episodes: number;
  minutes: number;
  error: string;
};
export type Manga = {
  id: string;
  title: string;
  description: string;
  cover: string;
  banner?: string;
  status: string;
  languages: string[];
};
export type MangaCategory = { id: string; name: string };
export type MangaDiscovery = {
  featured: Manga[];
  popular: Manga[];
  recentlyUpdated: Manga[];
  publishing: Manga[];
  categories: MangaCategory[];
  warning: string;
};
export type Chapter = {
  id: string;
  title: string;
  number: string;
  volume: string;
  language: string;
  pages: number;
  group?: string;
};
export type MangaProgress = {
  manga: Manga;
  chapter: Chapter;
  page: number;
  updated: number;
};
export type PlayerEvent = {
  state: {
    playing: boolean;
    paused: boolean;
    position: number;
    duration: number;
    eof: boolean;
    watched: boolean;
    error: string;
    session: string;
    videoCodec: string;
    audioCodec: string;
    width: number;
    height: number;
  };
  anime: Anime;
  episode: Episode;
};
export type Update = {
  version: string;
  notes: string;
  url: string;
  name: string;
  checksumUrl: string;
  available: boolean;
  managed: boolean;
};
export const key = (a: Anime) => a.provider + ":" + a.id;
