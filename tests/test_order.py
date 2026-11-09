"""Тесты порядка загрузки зависимостей."""

import unittest

from depviz.order import load_order
from depviz.report import format_load_order
from tests.test_graph import build


def names_in_order(description: dict[str, list[str]], depth: int) -> list[str]:
    """Возвращает имена пакетов в порядке загрузки."""
    graph = build(description, "A", depth)
    return [graph.names[key] for key in load_order(graph)]


class LoadOrderTests(unittest.TestCase):
    """Проверка порядка загрузки."""

    def test_chain(self) -> None:
        """Цепочка загружается от самой глубокой зависимости к корню."""
        order = names_in_order({"A": ["B"], "B": ["C"]}, 5)
        self.assertEqual(order, ["C", "B", "A"])

    def test_root_without_dependencies(self) -> None:
        """Пакет без зависимостей загружается один."""
        self.assertEqual(names_in_order({}, 5), ["A"])

    def test_diamond(self) -> None:
        """Общая зависимость загружается один раз и до зависимых."""
        description = {"A": ["B", "C"], "B": ["D"], "C": ["D"]}
        order = names_in_order(description, 5)
        self.assertEqual(order, ["D", "B", "C", "A"])

    def test_dependencies_precede_dependents(self) -> None:
        """В порядке без циклов каждая зависимость идёт раньше зависимого."""
        description = {
            "A": ["B", "C", "E"],
            "B": ["D"],
            "C": ["D", "E"],
            "D": ["F"],
            "E": ["F"],
        }
        graph = build(description, "A", 10)
        position = {key: i for i, key in enumerate(load_order(graph))}
        for source, targets in graph.edges.items():
            for target in targets:
                self.assertLess(position[target], position[source])

    def test_cycle_does_not_hang(self) -> None:
        """Цикл не мешает построить порядок, корень остаётся последним."""
        order = names_in_order({"A": ["B"], "B": ["C"], "C": ["A"]}, 10)
        self.assertEqual(order, ["C", "B", "A"])

    def test_depth_limit(self) -> None:
        """Пакеты глубже предела в порядок не попадают."""
        order = names_in_order({"A": ["B"], "B": ["C"]}, 1)
        self.assertEqual(order, ["B", "A"])

    def test_each_package_once(self) -> None:
        """Каждый пакет встречается в порядке ровно один раз."""
        description = {"A": ["B", "C"], "B": ["C"], "C": ["B"]}
        graph = build(description, "A", 10)
        order = load_order(graph)
        self.assertEqual(len(order), len(set(order)))
        self.assertEqual(len(order), len(graph.names))


class FormatTests(unittest.TestCase):
    """Проверка вывода порядка загрузки."""

    def test_numbered_list(self) -> None:
        """Порядок выводится нумерованным списком."""
        graph = build({"A": ["B"]}, "A", 5)
        lines = format_load_order(graph, load_order(graph))
        self.assertEqual(
            lines,
            [
                "Порядок загрузки зависимостей пакета A:",
                "  1. B",
                "  2. A",
            ],
        )


if __name__ == "__main__":
    unittest.main()
