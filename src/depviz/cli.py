"""Интерфейс командной строки."""

import argparse
import sys
from collections.abc import Sequence

from depviz.config import Config, load_config
from depviz.d2 import render_svg, to_d2, write_d2
from depviz.errors import ConfigError, RenderError, RepositoryError
from depviz.graph import DependencyGraph, GraphBuilder
from depviz.order import load_order
from depviz.report import format_graph, format_load_order
from depviz.repository import create_repository, root_version

DEFAULT_CONFIG = "config.toml"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_REPOSITORY_ERROR = 3
EXIT_RENDER_ERROR = 4


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
    parser.add_argument(
        "--graph",
        action="store_true",
        help="дополнительно вывести граф списком смежности",
    )
    parser.add_argument(
        "--order",
        action="store_true",
        help="дополнительно вывести порядок загрузки зависимостей",
    )
    return parser.parse_args(argv)


def build_graph(config: Config) -> DependencyGraph:
    """Строит граф зависимостей по параметрам конфигурации."""
    repository = create_repository(config)
    builder = GraphBuilder(repository, config.max_depth)
    return builder.build(config.package_name, root_version(config))


def visualize(graph: DependencyGraph, output_file: str) -> None:
    """Формирует D2, сохраняет его и изображение SVG, выводит результат."""
    text = to_d2(graph)
    d2_path = write_d2(text, output_file)
    print(f"Граф в формате D2 (файл {d2_path}):\n{text.rstrip()}")
    render_svg(d2_path, output_file)
    print(f"Изображение графа сохранено: {output_file}")


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа: строит граф и сохраняет его изображение в SVG."""
    args = parse_args(argv)
    try:
        config = load_config(args.config)
        graph = build_graph(config)
        if args.graph:
            print("\n".join(format_graph(graph, config.max_depth)))
        if args.order:
            print("\n".join(format_load_order(graph, load_order(graph))))
        visualize(graph, config.output_file)
    except ConfigError as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except RepositoryError as error:
        print(f"Ошибка репозитория: {error}", file=sys.stderr)
        return EXIT_REPOSITORY_ERROR
    except RenderError as error:
        print(f"Ошибка визуализации: {error}", file=sys.stderr)
        return EXIT_RENDER_ERROR
    return EXIT_OK
