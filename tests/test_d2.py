"""Тесты формирования D2 и получения SVG."""

import sys
import unittest
from pathlib import Path

from depviz.d2 import d2_path_for, render_svg, to_d2, write_d2
from depviz.errors import RenderError
from tests.helpers import temp_dir
from tests.test_graph import build

FAKE_D2 = (sys.executable, str(Path(__file__).with_name("fake_d2.py")))
FAILING = (sys.executable, "-c", "import sys; sys.exit(3)")


class ToD2Tests(unittest.TestCase):
    """Проверка текста на языке D2."""

    def test_nodes_and_edges(self) -> None:
        """Вершины получают подписи, рёбра — идентификаторы вершин."""
        text = to_d2(build({"A": ["B", "C"], "B": ["C"]}, "A", 5))
        lines = text.splitlines()
        self.assertEqual(lines[0], "direction: down")
        self.assertIn('n1: "B"', lines)
        self.assertIn('n2: "C"', lines)
        self.assertIn("n0 -> n1", lines)
        self.assertIn("n0 -> n2", lines)
        self.assertIn("n1 -> n2", lines)

    def test_root_is_highlighted(self) -> None:
        """Корневой пакет выделяется цветом."""
        text = to_d2(build({"A": ["B"]}, "A", 5))
        self.assertIn('n0: "A" {\n  style.fill: "#cfe8ff"\n}', text)

    def test_cycle_edge_is_marked(self) -> None:
        """Ребро, замыкающее цикл, подписано и выделено цветом."""
        text = to_d2(build({"A": ["B"], "B": ["A"]}, "A", 5))
        self.assertIn('n1 -> n0: "цикл" {', text)
        self.assertIn("n0 -> n1\n", text)

    def test_unexpanded_node_is_dashed(self) -> None:
        """Вершина на пределе глубины рисуется пунктиром."""
        text = to_d2(build({"A": ["B"], "B": ["C"]}, "A", 1))
        self.assertIn("style.stroke-dash: 3", text)
        self.assertNotIn("C", text)

    def test_labels_are_escaped(self) -> None:
        """Кавычки и обратная косая черта в подписях экранируются."""
        text = to_d2(build({'A': ['B"\\C']}, "A", 5))
        self.assertIn('n1: "B\\"\\\\C"', text)

    def test_names_with_dots_are_safe(self) -> None:
        """Точки в именах пакетов не превращаются во вложенность D2."""
        description = {"Lib.Core": ["Lib.Core.Abstractions"]}
        text = to_d2(build(description, "Lib.Core", 5))
        self.assertIn('n1: "Lib.Core.Abstractions"', text)
        self.assertIn("n0 -> n1", text)


class RenderTests(unittest.TestCase):
    """Проверка записи D2 и запуска d2."""

    def test_d2_path_is_next_to_svg(self) -> None:
        """Файл D2 лежит рядом с изображением и имеет то же имя."""
        self.assertEqual(d2_path_for("out/g.svg"), Path("out/g.d2"))

    def test_write_and_render(self) -> None:
        """Текст D2 записывается, программа d2 создаёт SVG."""
        with temp_dir() as directory:
            svg = str(directory / "nested" / "g.svg")
            d2_file = write_d2("a -> b\n", svg)
            render_svg(d2_file, svg, FAKE_D2)
            self.assertEqual(d2_file.read_text(encoding="utf-8"), "a -> b\n")
            self.assertTrue(Path(svg).is_file())

    def test_missing_d2(self) -> None:
        """Отсутствие программы d2 даёт понятную ошибку."""
        with temp_dir() as directory:
            svg = str(directory / "g.svg")
            with self.assertRaises(RenderError) as context:
                render_svg(directory / "g.d2", svg, ("no-such-d2-binary",))
        self.assertIn("не найдена", str(context.exception))

    def test_failing_d2(self) -> None:
        """Ненулевой код возврата d2 превращается в RenderError."""
        with temp_dir() as directory:
            with self.assertRaises(RenderError) as context:
                render_svg(directory / "g.d2", "g.svg", FAILING)
        self.assertIn("завершился с ошибкой", str(context.exception))


if __name__ == "__main__":
    unittest.main()
