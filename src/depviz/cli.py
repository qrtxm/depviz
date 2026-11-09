"""Интерфейс командной строки."""

import argparse
import sys
from collections.abc import Sequence

from depviz.config import MODE_TEST, load_config
from depviz.errors import ConfigError, RepositoryError
from depviz.nuget import get_direct_dependencies

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


def format_dependencies(
    name: str, version: str, dependencies: list[tuple[str, str]]
) -> list[str]:
    """Формирует строки отчёта о прямых зависимостях пакета."""
    lines = [f"Прямые зависимости пакета {name} {version}:"]
    if not dependencies:
        lines.append("  (нет)")
    for dep_name, dep_version in dependencies:
        lines.append(f"  {dep_name} {dep_version}")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа: выводит прямые зависимости заданного пакета."""
    args = parse_args(argv)
    try:
        config = load_config(args.config)
        if config.repository_mode == MODE_TEST:
            raise RepositoryError("тестовый режим появится на этапе 3")
        dependencies = get_direct_dependencies(
            config.repository, config.package_name, config.package_version
        )
    except ConfigError as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except RepositoryError as error:
        print(f"Ошибка репозитория: {error}", file=sys.stderr)
        return EXIT_REPOSITORY_ERROR
    name, version = config.package_name, config.package_version
    print("\n".join(format_dependencies(name, version, dependencies)))
    return EXIT_OK
