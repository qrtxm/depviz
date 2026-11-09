"""Источники данных о зависимостях: NuGet и тестовый файл."""

import re
from pathlib import Path

from depviz.config import MODE_TEST, Config
from depviz.errors import RepositoryError
from depviz.graph import Repository
from depviz.nuget import get_direct_dependencies

TEST_NAME = re.compile(r"[A-Z]+")
LIST_SEPARATOR = re.compile(r"[\s,]+")
COMMENT_MARK = "#"
DEFINITION_MARK = ":"
TEST_VERSION = ""


class NugetRepository:
    """Репозиторий NuGet, доступный по URL; ответы кэшируются."""

    def __init__(self, base_url: str) -> None:
        """Запоминает URL репозитория и создаёт пустой кэш."""
        self._base_url = base_url
        self._cache: dict[tuple[str, str], list[tuple[str, str]]] = {}

    def dependencies(self, name: str, version: str) -> list[tuple[str, str]]:
        """Возвращает прямые зависимости пакета, обращаясь к сети один раз."""
        key = (name.casefold(), version)
        if key not in self._cache:
            self._cache[key] = get_direct_dependencies(
                self._base_url, name, version
            )
        return self._cache[key]


class FileRepository:
    """Тестовый репозиторий, описанный файлом: «A: B C» на каждой строке."""

    def __init__(self, graph: dict[str, list[str]]) -> None:
        """Сохраняет описание графа: пакет -> список его зависимостей."""
        self._graph = graph
        self._known = set(graph)
        for targets in graph.values():
            self._known.update(targets)

    def dependencies(self, name: str, version: str) -> list[tuple[str, str]]:
        """Возвращает зависимости пакета; версии в тестовом режиме нет."""
        if name not in self._known:
            raise RepositoryError(
                f"пакет {name} не найден в тестовом репозитории"
            )
        return [(target, TEST_VERSION) for target in self._graph.get(name, [])]


def load_test_graph(path: str) -> dict[str, list[str]]:
    """Читает файл описания графа тестового репозитория."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RepositoryError(f"не удалось прочитать {path}: {error}") from None
    graph: dict[str, list[str]] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        _parse_test_line(graph, line, number)
    return graph


def create_repository(config: Config) -> Repository:
    """Создаёт репозиторий в соответствии с режимом работы из конфигурации."""
    if config.repository_mode == MODE_TEST:
        return FileRepository(load_test_graph(config.repository))
    return NugetRepository(config.repository)


def root_version(config: Config) -> str:
    """Версия корневого пакета: в тестовом режиме версий нет."""
    if config.repository_mode == MODE_TEST:
        return TEST_VERSION
    return config.package_version


def _parse_test_line(
    graph: dict[str, list[str]], line: str, number: int
) -> None:
    """Разбирает одну строку файла и добавляет описание пакета в graph."""
    content = line.partition(COMMENT_MARK)[0].strip()
    if not content:
        return
    name, mark, rest = content.partition(DEFINITION_MARK)
    name = name.strip()
    targets = [item for item in LIST_SEPARATOR.split(rest.strip()) if item]
    if not mark or not TEST_NAME.fullmatch(name):
        raise RepositoryError(f"строка {number}: ожидается «A: B C»")
    for target in targets:
        if not TEST_NAME.fullmatch(target):
            raise RepositoryError(
                f"строка {number}: имя {target!r} должно состоять "
                "из больших латинских букв"
            )
    if name in graph:
        raise RepositoryError(f"строка {number}: пакет {name} описан дважды")
    graph[name] = targets
