"""Интерфейс командной строки."""

import argparse
import sys
from collections.abc import Sequence

from depviz.config import load_config
from depviz.errors import ConfigError, RepositoryError
from depviz.graph import GraphBuilder
from depviz.order import load_order
from depviz.report import format_load_order
from depviz.repository import create_repository, root_version

DEFAULT_CONFIG = "config.toml"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_REPOSITORY_ERROR = 3


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
    """Точка входа: выводит порядок загрузки зависимостей пакета."""
    args = parse_args(argv)
    try:
        config = load_config(args.config)
        repository = create_repository(config)
        builder = GraphBuilder(repository, config.max_depth)
        graph = builder.build(config.package_name, root_version(config))
    except ConfigError as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except RepositoryError as error:
        print(f"Ошибка репозитория: {error}", file=sys.stderr)
        return EXIT_REPOSITORY_ERROR
    print("\n".join(format_load_order(graph, load_order(graph))))
    return EXIT_OK
