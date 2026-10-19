from __future__ import annotations

import argparse


APP_NAME = "animecaos"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="GUI responsiva para buscar e assistir anime.",
    )
    parser.add_argument("--debug", "-d", action="store_true", help="Ativa modo debug.")
    parser.add_argument("--cli", action="store_true", help="Executa fluxo antigo em terminal.")
    parser.add_argument("--query", "-q", help="Busca inicial no modo CLI.")
    parser.add_argument(
        "--continue_watching",
        "-c",
        action="store_true",
        help="Continua do historico no modo CLI.",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cli:
        from animecaos.ui.cli.app import run_cli

        run_cli(args)
        return 0

    from animecaos.ui.gui.app import run_gui

    return run_gui(debug=args.debug)
