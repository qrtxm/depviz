"""Интерфейс командной строки."""

import argparse
import sys
from collections.abc import Sequence

from depviz.config import format_parameters, load_config
from depviz.errors import ConfigError

DEFAULT_CONFIG = "config.toml"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 2


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(
        prog="depviz",
        description="Визуализация графа зависимостей пакетов NuGet.",
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=DEFAULT_CONFIG,
        help="путь к конфигурационному файлу TOML (по умолчанию "
        f"{DEFAULT_CONFIG})",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа: выводит параметры конфигурации и возвращает код."""
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    for line in format_parameters(config):
        print(line)
    return EXIT_OK
