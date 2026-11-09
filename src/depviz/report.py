"""Текстовое представление графа зависимостей для вывода на экран."""

from depviz.graph import DependencyGraph

ARROW = " -> "
NO_DEPENDENCIES = "нет зависимостей"
DEPTH_LIMIT_NOTE = "глубина анализа исчерпана"


def format_graph(graph: DependencyGraph, max_depth: int) -> list[str]:
    """Формирует строки отчёта: список смежности и найденные циклы."""
    lines = [
        f"Граф зависимостей пакета {graph.label(graph.root)} "
        f"(максимальная глубина {max_depth}):"
    ]
    for key in graph.names:
        lines.append(f"  {_describe_node(graph, key)}")
    lines.append("Циклические зависимости:")
    if not graph.cycles:
        lines.append("  не обнаружены")
    for cycle in graph.cycles:
        lines.append("  " + ARROW.join(graph.label(key) for key in cycle))
    return lines


def _describe_node(graph: DependencyGraph, key: str) -> str:
    """Описывает вершину: её подпись и список прямых зависимостей."""
    targets = graph.edges[key]
    if targets:
        listed = ", ".join(graph.label(target) for target in targets)
        return f"{graph.label(key)}{ARROW}{listed}"
    if key in graph.unexpanded:
        return f"{graph.label(key)} ({DEPTH_LIMIT_NOTE})"
    return f"{graph.label(key)} ({NO_DEPENDENCIES})"


def format_load_order(graph: DependencyGraph, order: list[str]) -> list[str]:
    """Формирует нумерованный список пакетов в порядке загрузки."""
    lines = [
        f"Порядок загрузки зависимостей пакета {graph.label(graph.root)}:"
    ]
    for number, key in enumerate(order, start=1):
        lines.append(f"  {number}. {graph.label(key)}")
    return lines
