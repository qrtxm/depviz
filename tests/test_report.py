"""Тесты текстового отчёта о графе."""

import unittest

from depviz.graph import GraphBuilder
from depviz.report import format_graph
from tests.test_graph import DictRepository


def report(description: dict[str, list[str]], depth: int) -> list[str]:
    """Строит граф в памяти и возвращает строки отчёта."""
    builder = GraphBuilder(DictRepository(description), depth)
    return format_graph(builder.build("A", ""), depth)


class ReportTests(unittest.TestCase):
    """Проверка формата вывода графа."""

    def test_adjacency_list(self) -> None:
        """Каждая вершина выводится вместе со своими зависимостями."""
        lines = report({"A": ["B", "C"], "B": ["C"]}, 5)
        self.assertIn("  A -> B, C", lines)
        self.assertIn("  B -> C", lines)
        self.assertIn("  C (нет зависимостей)", lines)
        self.assertIn("  не обнаружены", lines)

    def test_depth_limit_note(self) -> None:
        """Вершины на пределе глубины помечаются."""
        lines = report({"A": ["B"], "B": ["C"]}, 1)
        self.assertIn("  B (глубина анализа исчерпана)", lines)

    def test_cycle_is_listed(self) -> None:
        """Циклы перечисляются в отчёте."""
        lines = report({"A": ["B"], "B": ["A"]}, 5)
        self.assertIn("  A -> B -> A", lines)


if __name__ == "__main__":
    unittest.main()
