from sys import exit

try:
    import curses
except ModuleNotFoundError:
    curses = None


def _safe_addstr(stdscr, y: int, x: int, text: str, attr=0):
    try:
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        # Ignore draw errors on very small terminals.
        pass


def _menu(stdscr, options: list[str], msg: str, result: list[str]) -> None:
    stdscr.clear()
    curses.curs_set(0)

    curses.start_color()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    current_option = 0
    start_index = 0

    while True:
        stdscr.clear()
        screen_height, screen_width = stdscr.getmaxyx()
        display_height = max(1, screen_height - 3)

        title_x = max(0, (screen_width - len(msg)) // 2)
        _safe_addstr(stdscr, 0, title_x, msg.upper(), curses.color_pair(2))

        end_index = start_index + display_height
        visible_options = options[start_index:min(len(options), end_index)]

        for idx, row in enumerate(visible_options):
            y = idx + 2
            row_text = row[: max(1, screen_width - 4)]
            if start_index + idx == current_option:
                _safe_addstr(stdscr, y, 2, row_text, curses.color_pair(1))
            else:
                _safe_addstr(stdscr, y, 2, row_text)

        key = stdscr.getch()

        if key == curses.KEY_UP:
            current_option = (current_option - 1) % len(options)
            if current_option < start_index:
                start_index = current_option
            elif current_option == len(options) - 1 and display_height < len(options):
                start_index = current_option - display_height + 1

        elif key == curses.KEY_DOWN:
            current_option = (current_option + 1) % len(options)
            if current_option >= end_index or current_option == 0:
                start_index = current_option

        elif key == curses.KEY_ENTER or key in (10, 13):
            result.append(options[current_option])
            break


def menu(opts: list[str], msg: str = "") -> str:
    options = list(opts)
    options.append("Sair")

    if curses is None:
        return _menu_fallback(options, msg)

    selected = []
    curses.wrapper(lambda stdscr: _menu(stdscr, options, msg, result=selected))

    if selected[0] == "Sair":
        exit()
    return selected[0]


def _menu_fallback(options: list[str], msg: str) -> str:
    prompt = msg or "Escolha uma opcao"
    while True:
        print(f"\n{prompt}:")
        for idx, option in enumerate(options, start=1):
            print(f"{idx}. {option}")

        try:
            selected = int(input("Numero: ").strip())
        except ValueError:
            print("Entrada invalida.")
            continue

        if selected < 1 or selected > len(options):
            print("Opcao fora da faixa.")
            continue

        value = options[selected - 1]
        if value == "Sair":
            exit()
        return value
