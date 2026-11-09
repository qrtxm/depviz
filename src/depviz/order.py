"""Порядок загрузки зависимостей."""

from depviz.graph import DependencyGraph


def load_order(graph: DependencyGraph) -> list[str]:
    """Возвращает ключи вершин в порядке загрузки.

    Каждый пакет стоит после всех своих зависимостей (обратный
    топологический порядок, получаемый обходом в глубину), корневой
    пакет — последний. Для циклов порядок внутри цикла определяется
    направлением обхода: ребро, замыкающее цикл, игнорируется.
    """
    order: list[str] = []
    _postorder(graph, graph.root, set(), order)
    return order


def _postorder(
    graph: DependencyGraph, key: str, visited: set[str], order: list[str]
) -> None:
    """Рекурсивно добавляет в order вершину после всех её зависимостей."""
    visited.add(key)
    for target in graph.edges[key]:
        if target not in visited:
            _postorder(graph, target, visited, order)
    order.append(key)
