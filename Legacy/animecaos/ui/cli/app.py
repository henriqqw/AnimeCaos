import os
from json import JSONDecodeError, dump, load
from pathlib import Path
from sys import exit

from animecaos.core import loader
from animecaos.core.repository import rep
from animecaos.player.video_player import play_video

from .menu import menu

APP_NAME = "AnimeCaos"
LEGACY_APP_NAME = "animecaos"


def _history_dir(app_name: str) -> Path:
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / app_name
        return Path.home() / "AppData" / "Roaming" / app_name
    return Path.home() / ".local" / "state" / app_name


HISTORY_FILE = _history_dir(APP_NAME) / "history.json"
LEGACY_HISTORY_FILE = _history_dir(LEGACY_APP_NAME) / "history.json"


def run_cli(args) -> None:
    loader.load_plugins({"pt-br"}, ["animesonlinecc"] if args.debug else None)

    if args.continue_watching:
        selected_anime, episode_idx = load_history()
    else:
        query = args.query or (None if args.debug else input("Pesquise anime: "))
        query = query or "eva"
        rep.search_anime(query)
        titles = rep.get_anime_titles()
        if not titles:
            print("Nenhum anime encontrado.")
            exit(1)

        selected_anime = menu(titles, msg="Escolha o anime.")
        rep.search_episodes(selected_anime)
        episode_list = rep.get_episode_list(selected_anime)
        if not episode_list:
            print("Nenhum episodio encontrado.")
            exit(1)

        selected_episode = menu(episode_list, msg="Escolha o episodio.")
        episode_idx = episode_list.index(selected_episode)

    episode_lengths = [len(urls) for urls, _ in rep.anime_episodes_urls[selected_anime]]
    num_episodes = max(episode_lengths, default=0)
    if num_episodes == 0:
        print("Nao foi possivel carregar episodios para esse anime.")
        exit(1)

    while True:
        episode_num = episode_idx + 1
        try:
            player_url = rep.search_player(selected_anime, episode_num)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Falha ao carregar player do episodio {episode_num}: {exc}")
            exit(1)

        if args.debug:
            print(f"[debug] episodio={episode_num} url={player_url}")
        play_video(player_url, args.debug)
        save_history(selected_anime, episode_idx)

        options = []
        if episode_idx < num_episodes - 1:
            options.append("Proximo")
        if episode_idx > 0:
            options.append("Anterior")
        if not options:
            print("Fim da lista de episodios.")
            return

        selected_opt = menu(options, msg="O que quer fazer agora?")
        if selected_opt == "Proximo":
            episode_idx += 1
        elif selected_opt == "Anterior":
            episode_idx -= 1


def load_history() -> tuple[str, int]:
    history_file = HISTORY_FILE if HISTORY_FILE.exists() else LEGACY_HISTORY_FILE

    try:
        with history_file.open("r", encoding="utf-8") as history_fp:
            data = load(history_fp)
    except FileNotFoundError:
        print("Sem historico de animes.")
        exit(1)
    except PermissionError:
        print("Sem permissao para ler o historico.")
        exit(1)
    except JSONDecodeError:
        print("Historico corrompido. Apague o arquivo e tente novamente.")
        exit(1)

    if not data:
        print("Sem historico de animes.")
        exit(1)

    title_suffix_sizes = {}
    menu_titles = []
    for anime, info in data.items():
        episode_idx = info[1]
        suffix = f" (ultimo episodio assistido {episode_idx + 1})"
        item = anime + suffix
        title_suffix_sizes[item] = len(suffix)
        menu_titles.append(item)

    selected = menu(menu_titles, msg="Continue assistindo.")
    anime = selected[: -title_suffix_sizes[selected]]
    episode_idx = data[anime][1]
    rep.anime_episodes_urls[anime] = data[anime][0]
    return anime, episode_idx


def save_history(anime: str, episode_idx: int) -> None:
    history_file = HISTORY_FILE if HISTORY_FILE.exists() else LEGACY_HISTORY_FILE
    data = {}
    try:
        if history_file.exists():
            with history_file.open("r", encoding="utf-8") as history_fp:
                data = load(history_fp)
    except (PermissionError, JSONDecodeError):
        print("Nao foi possivel ler historico anterior. Um novo arquivo sera criado.")

    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data[anime] = [rep.anime_episodes_urls[anime], episode_idx]
        with HISTORY_FILE.open("w", encoding="utf-8") as history_fp:
            dump(data, history_fp, ensure_ascii=False, indent=2)
    except PermissionError:
        print("Nao ha permissao para salvar historico.")
