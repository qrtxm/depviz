"""Загрузка и проверка конфигурации в формате TOML."""

import re
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from depviz.errors import ConfigError

MODE_REMOTE = "remote"
MODE_TEST = "test"
VALID_MODES = (MODE_REMOTE, MODE_TEST)
MIN_DEPTH = 1
MAX_DEPTH_LIMIT = 100
OUTPUT_SUFFIX = ".svg"
URL_SCHEMES = ("http", "https")
VERSION_PATTERN = re.compile(
    r"\d+(\.\d+){0,3}(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?"
)
NUGET_ID_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")
TEST_NAME_PATTERN = re.compile(r"[A-Z]+")


@dataclass(frozen=True)
class Config:
    """Параметры, настраиваемые пользователем."""

    package_name: str
    package_version: str
    repository: str
    repository_mode: str
    output_file: str
    max_depth: int


def load_config(path: str) -> Config:
    """Читает TOML-файл, проверяет все параметры и возвращает Config."""
    data = _read_toml(Path(path))
    _check_keys(data)
    values = {field.name: data[field.name] for field in fields(Config)}
    _check_types(values)
    config = Config(**values)
    _check_values(config)
    return config


def format_parameters(config: Config) -> list[str]:
    """Возвращает параметры конфигурации в виде строк «ключ = значение»."""
    return [
        f"{field.name} = {getattr(config, field.name)!r}"
        for field in fields(Config)
    ]


def _read_toml(path: Path) -> dict[str, Any]:
    """Читает и разбирает TOML-файл, преобразуя сбои в ConfigError."""
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except FileNotFoundError:
        raise ConfigError(f"файл конфигурации не найден: {path}") from None
    except OSError as error:
        raise ConfigError(f"не удалось прочитать {path}: {error}") from None
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ConfigError(f"некорректный TOML в {path}: {error}") from None


def _check_keys(data: dict[str, Any]) -> None:
    """Проверяет, что заданы все параметры и нет неизвестных."""
    known = {field.name for field in fields(Config)}
    missing = sorted(known - data.keys())
    unknown = sorted(data.keys() - known)
    if missing:
        raise ConfigError("не заданы параметры: " + ", ".join(missing))
    if unknown:
        raise ConfigError("неизвестные параметры: " + ", ".join(unknown))


def _check_types(values: dict[str, Any]) -> None:
    """Проверяет типы значений: строки непустые, глубина целая."""
    for field in fields(Config):
        value = values[field.name]
        if field.type is int:
            _require_int(field.name, value)
        else:
            _require_text(field.name, value)


def _require_int(name: str, value: Any) -> None:
    """Требует целое число (булево значение целым не считается)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"параметр {name} должен быть целым числом")


def _require_text(name: str, value: Any) -> None:
    """Требует непустую строку."""
    if not isinstance(value, str):
        raise ConfigError(f"параметр {name} должен быть строкой")
    if not value.strip():
        raise ConfigError(f"параметр {name} не должен быть пустым")


def _check_values(config: Config) -> None:
    """Проверяет значения параметров на допустимость."""
    if config.repository_mode not in VALID_MODES:
        raise ConfigError(
            "repository_mode должен быть 'remote' или 'test', "
            f"получено {config.repository_mode!r}"
        )
    _check_package(config)
    _check_repository(config)
    _check_output(config.output_file)
    _check_depth(config.max_depth)


def _check_package(config: Config) -> None:
    """Проверяет имя и версию пакета с учётом режима работы."""
    if config.repository_mode == MODE_TEST:
        pattern, hint = TEST_NAME_PATTERN, "большие латинские буквы"
    else:
        pattern, hint = NUGET_ID_PATTERN, "латиница, цифры, '.', '_', '-'"
    if not pattern.fullmatch(config.package_name):
        raise ConfigError(
            f"package_name {config.package_name!r} недопустимо: {hint}"
        )
    if not VERSION_PATTERN.fullmatch(config.package_version):
        raise ConfigError(
            f"package_version {config.package_version!r} не похоже "
            "на версию (пример: 13.0.3 или 1.0.0-beta.1)"
        )


def _check_repository(config: Config) -> None:
    """Проверяет URL репозитория или путь к файлу тестового репозитория."""
    if config.repository_mode == MODE_TEST:
        if not Path(config.repository).is_file():
            raise ConfigError(
                f"файл тестового репозитория не найден: {config.repository}"
            )
        return
    parts = urlparse(config.repository)
    if parts.scheme not in URL_SCHEMES or not parts.netloc:
        raise ConfigError(
            f"repository {config.repository!r} не является URL http(s)"
        )


def _check_output(output_file: str) -> None:
    """Проверяет имя файла с изображением графа."""
    path = Path(output_file)
    if path.suffix.lower() != OUTPUT_SUFFIX:
        raise ConfigError(
            f"output_file {output_file!r} должен иметь расширение .svg"
        )
    if path.is_dir():
        raise ConfigError(f"output_file {output_file!r} является каталогом")


def _check_depth(max_depth: int) -> None:
    """Проверяет, что максимальная глубина лежит в допустимых границах."""
    if not MIN_DEPTH <= max_depth <= MAX_DEPTH_LIMIT:
        raise ConfigError(
            f"max_depth должен быть от {MIN_DEPTH} до {MAX_DEPTH_LIMIT}, "
            f"получено {max_depth}"
        )
