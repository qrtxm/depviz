"""Тесты построения графа зависимостей."""

import unittest

from depviz.graph import DependencyGraph, GraphBuilder, node_key


class DictRepository:
    """Репозиторий в памяти: пакет -> список имён зависимостей."""

    def __init__(self, graph: dict[str, list[str]]) -> None:
        """Сохраняет описание графа и журнал обращений."""
        self.graph = graph
        self.calls: list[str] = []

    def dependencies(self, name: str, version: str) -> list[tuple[str, str]]:
        """Возвращает зависимости пакета без версий."""
        self.calls.append(name)
        return [(target, "") for target in self.graph.get(name, [])]


def build(
    description: dict[str, list[str]], root: str, depth: int
) -> DependencyGraph:
    """Строит граф по описанию в памяти."""
    return GraphBuilder(DictRepository(description), depth).build(root, "")


def edges_of(graph: DependencyGraph) -> dict[str, list[str]]:
    """Возвращает рёбра графа в виде имён пакетов."""
    return {
        graph.names[key]: [graph.names[target] for target in targets]
        for key, targets in graph.edges.items()
    }


class BuildGraphTests(unittest.TestCase):
    """Проверка обхода в глубину."""

    def test_chain(self) -> None:
        """Цепочка зависимостей обходится целиком."""
        graph = build({"A": ["B"], "B": ["C"]}, "A", 5)
        self.assertEqual(edges_of(graph), {"A": ["B"], "B": ["C"], "C": []})
        self.assertEqual(graph.cycles, [])

    def test_depth_limit(self) -> None:
        """Анализ не уходит глубже заданного предела."""
        graph = build({"A": ["B"], "B": ["C"], "C": ["D"]}, "A", 2)
        self.assertEqual(list(graph.names.values()), ["A", "B", "C"])
        self.assertEqual(graph.unexpanded, {node_key("C")})

    def test_depth_one_only_direct(self) -> None:
        """При глубине 1 строятся только прямые зависимости."""
        graph = build({"A": ["B", "C"], "B": ["D"]}, "A", 1)
        self.assertEqual(edges_of(graph), {"A": ["B", "C"], "B": [], "C": []})

    def test_diamond_has_no_duplicates(self) -> None:
        """Общая зависимость присутствует в графе один раз."""
        description = {"A": ["B", "C"], "B": ["D"], "C": ["D"]}
        graph = build(description, "A", 5)
        self.assertEqual(len(graph.names), 4)
        self.assertEqual(edges_of(graph)["C"], ["D"])

    def test_preorder_discovery(self) -> None:
        """Вершины перечисляются в порядке обхода в глубину."""
        description = {"A": ["B", "C"], "B": ["D"]}
        graph = build(description, "A", 5)
        self.assertEqual(list(graph.names.values()), ["A", "B", "D", "C"])

    def test_node_found_shallower_is_expanded(self) -> None:
        """Вершина, впервые найденная на пределе глубины, дообходится."""
        description = {"A": ["B", "D"], "B": ["C"], "C": ["D"], "D": ["E"]}
        graph = build(description, "A", 2)
        self.assertEqual(edges_of(graph)["D"], ["E"])
        self.assertNotIn(node_key("D"), graph.unexpanded)

    def test_names_are_case_insensitive(self) -> None:
        """Имена пакетов, отличающиеся регистром, — одна вершина."""
        graph = build({"A": ["Lib", "lib"]}, "A", 3)
        self.assertEqual(len(graph.names), 2)


class CycleTests(unittest.TestCase):
    """Проверка обработки циклических зависимостей."""

    def test_simple_cycle(self) -> None:
        """Цикл A -> B -> A находится, обход завершается."""
        graph = build({"A": ["B"], "B": ["A"]}, "A", 10)
        self.assertEqual(graph.cycles, [("a", "b", "a")])
        self.assertEqual(edges_of(graph), {"A": ["B"], "B": ["A"]})

    def test_self_dependency(self) -> None:
        """Зависимость пакета от самого себя считается циклом."""
        graph = build({"A": ["A"]}, "A", 10)
        self.assertEqual(graph.cycles, [("a", "a")])

    def test_cycle_below_root(self) -> None:
        """Цикл, не включающий корень, тоже обнаруживается."""
        description = {"A": ["B"], "B": ["C"], "C": ["B"]}
        graph = build(description, "A", 10)
        self.assertEqual(graph.cycles, [("b", "c", "b")])

    def test_cycle_reported_once(self) -> None:
        """Один и тот же цикл не дублируется в списке."""
        description = {"A": ["B", "C"], "B": ["C"], "C": ["B"]}
        graph = build(description, "A", 10)
        self.assertEqual(len(graph.cycles), len(set(graph.cycles)))

    def test_cycle_with_small_depth_terminates(self) -> None:
        """Предел глубины действует и при наличии цикла."""
        graph = build({"A": ["B"], "B": ["A"]}, "A", 1)
        self.assertEqual(graph.cycles, [])
        self.assertEqual(edges_of(graph), {"A": ["B"], "B": []})


class RecursionTests(unittest.TestCase):
    """Проверка вспомогательных свойств построителя."""

    def test_repository_asked_once_per_expansion(self) -> None:
        """Каждая вершина без повторного обхода запрашивается один раз."""
        repository = DictRepository({"A": ["B", "C"], "B": ["D"], "C": ["D"]})
        GraphBuilder(repository, 5).build("A", "")
        self.assertEqual(repository.calls, ["A", "B", "D", "C"])

    def test_shallower_revisit_asks_again(self) -> None:
        """Повторный обход на меньшей глубине допустим, но конечен."""
        repository = DictRepository({"A": ["B", "C"], "B": ["C"]})
        GraphBuilder(repository, 5).build("A", "")
        self.assertEqual(repository.calls, ["A", "B", "C", "C"])

    def test_label(self) -> None:
        """Подпись вершины содержит версию, если она известна."""
        graph = DependencyGraph(root="a")
        graph.add_node("A", "1.0.0")
        graph.add_node("B", "")
        self.assertEqual(graph.label("a"), "A 1.0.0")
        self.assertEqual(graph.label("b"), "B")


if __name__ == "__main__":
    unittest.main()
