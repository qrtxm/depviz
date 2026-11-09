"""Граф зависимостей и его построение поиском в глубину (DFS)."""

from dataclasses import dataclass, field
from typing import Protocol


class Repository(Protocol):
    """Источник данных: прямые зависимости пакета как пары (имя, версия)."""

    def dependencies(self, name: str, version: str) -> list[tuple[str, str]]:
        """Возвращает прямые зависимости пакета."""


def node_key(name: str) -> str:
    """Возвращает ключ вершины: имена пакетов не зависят от регистра."""
    return name.casefold()


@dataclass
class DependencyGraph:
    """Ориентированный граф: ребро A -> B означает «A зависит от B»."""

    root: str
    names: dict[str, str] = field(default_factory=dict)
    versions: dict[str, str] = field(default_factory=dict)
    edges: dict[str, list[str]] = field(default_factory=dict)
    cycles: list[tuple[str, ...]] = field(default_factory=list)
    unexpanded: set[str] = field(default_factory=set)

    def add_node(self, name: str, version: str) -> None:
        """Добавляет вершину, если её ещё нет (первая версия сохраняется)."""
        key = node_key(name)
        if key not in self.names:
            self.names[key] = name
            self.versions[key] = version
            self.edges[key] = []

    def add_edge(self, source: str, target: str) -> None:
        """Добавляет ребро между существующими вершинами без повторов."""
        if target not in self.edges[source]:
            self.edges[source].append(target)

    def label(self, key: str) -> str:
        """Возвращает подпись вершины: имя и, если известна, версия."""
        version = self.versions[key]
        return f"{self.names[key]} {version}" if version else self.names[key]


class GraphBuilder:
    """Строит граф зависимостей обходом в глубину с рекурсией."""

    def __init__(self, repository: Repository, max_depth: int) -> None:
        """Запоминает репозиторий и максимальную глубину анализа."""
        self._repository = repository
        self._max_depth = max_depth
        self._graph: DependencyGraph | None = None
        self._best_depth: dict[str, int] = {}
        self._path: list[str] = []

    def build(self, name: str, version: str) -> DependencyGraph:
        """Строит граф для пакета; корень лежит на глубине 0."""
        self._graph = DependencyGraph(root=node_key(name))
        self._best_depth = {}
        self._path = []
        self._visit(name, version, 0)
        return self._graph

    def _visit(self, name: str, version: str, depth: int) -> None:
        """Рекурсивно обходит зависимости пакета, лежащего на глубине depth."""
        graph = self._graph
        graph.add_node(name, version)
        key = node_key(name)
        self._best_depth[key] = depth
        if depth >= self._max_depth:
            graph.unexpanded.add(key)
            return
        graph.unexpanded.discard(key)
        self._path.append(key)
        found = self._repository.dependencies(name, graph.versions[key])
        for dep_name, dep_version in found:
            self._follow(key, dep_name, dep_version, depth + 1)
        self._path.pop()

    def _follow(
        self, source: str, name: str, version: str, depth: int
    ) -> None:
        """Обрабатывает ребро source -> name: цикл, повтор или новый обход."""
        graph = self._graph
        graph.add_node(name, version)
        target = node_key(name)
        graph.add_edge(source, target)
        if target in self._path:
            self._register_cycle(target)
        elif self._is_shallower(target, depth):
            self._visit(name, version, depth)

    def _is_shallower(self, key: str, depth: int) -> bool:
        """Истина, если вершина новая или найдена на меньшей глубине."""
        return key not in self._best_depth or depth < self._best_depth[key]

    def _register_cycle(self, target: str) -> None:
        """Запоминает цикл: путь от target до текущей вершины и обратно."""
        start = self._path.index(target)
        cycle = tuple(self._path[start:]) + (target,)
        if cycle not in self._graph.cycles:
            self._graph.cycles.append(cycle)
