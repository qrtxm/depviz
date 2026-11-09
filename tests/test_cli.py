"""Тесты интерфейса командной строки."""

import contextlib
import io
import unittest
from unittest import mock

from depviz.cli import (
    EXIT_CONFIG_ERROR,
    EXIT_OK,
    EXIT_RENDER_ERROR,
    EXIT_REPOSITORY_ERROR,
    main,
)
from depviz.errors import RenderError, RepositoryError
from tests.helpers import temp_dir, write_config

NUGET_TARGET = "depviz.repository.get_direct_dependencies"
RENDER_TARGET = "depviz.cli.render_svg"


def run_main(argv: list[str]) -> tuple[int, str, str]:
    """Запускает main с заглушкой d2 и возвращает код, stdout и stderr."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        with mock.patch(RENDER_TARGET):
            code = main(argv)
    return code, out.getvalue(), err.getvalue()


def run_test_mode(
    text: str, flags: tuple[str, ...] = (), **overrides: object
) -> tuple[int, str, str]:
    """Запускает приложение в тестовом режиме с графом из текста."""
    with temp_dir() as directory:
        repo = directory / "repo.txt"
        repo.write_text(text, encoding="utf-8")
        values = {
            "package_name": "A",
            "repository": repo.as_posix(),
            "repository_mode": "test",
            "output_file": (directory / "out" / "g.svg").as_posix(),
            **overrides,
        }
        return run_main([write_config(directory, **values), *flags])


class VisualizationTests(unittest.TestCase):
    """Проверка вывода D2 и сохранения изображения."""

    def test_prints_d2_and_reports_svg(self) -> None:
        """Выводится текст D2, затем сообщение о сохранённом SVG."""
        code, out, err = run_test_mode("A: B C\n", max_depth=5)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("Граф в формате D2", out)
        self.assertIn("n0 -> n1", out)
        self.assertIn("Изображение графа сохранено:", out)
        self.assertIn("g.svg", out)

    def test_render_error(self) -> None:
        """Ошибка d2 даёт сообщение в stderr и код 4."""
        failure = RenderError("d2 недоступна")
        with temp_dir() as directory:
            path = write_config(directory, repository_mode="remote")
            with mock.patch(NUGET_TARGET, return_value=[]):
                with mock.patch(RENDER_TARGET, side_effect=failure):
                    with contextlib.redirect_stderr(io.StringIO()) as err:
                        code = main([path])
        self.assertEqual(code, EXIT_RENDER_ERROR)
        self.assertIn("Ошибка визуализации: d2 недоступна", err.getvalue())


class TestModeTests(unittest.TestCase):
    """Проверка работы приложения с тестовым репозиторием."""

    def test_order_flag(self) -> None:
        """Флаг --order выводит порядок загрузки."""
        text = "A: B C\nB: D\nC: D\n"
        code, out, _err = run_test_mode(text, ("--order",), max_depth=5)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("  1. D\n  2. B\n  3. C\n  4. A", out)

    def test_graph_flag(self) -> None:
        """Флаг --graph выводит граф списком смежности."""
        _code, out, _err = run_test_mode("A: B\nB: A\n", ("--graph",))
        self.assertIn("  A -> B", out)
        self.assertIn("  A -> B -> A", out)

    def test_depth_is_respected(self) -> None:
        """Максимальная глубина из конфигурации ограничивает анализ."""
        _code, out, _err = run_test_mode(
            "A: B\nB: C\n", ("--order",), max_depth=1
        )
        self.assertIn("  1. B\n  2. A", out)
        self.assertNotIn("C", out)

    def test_cycle_does_not_hang(self) -> None:
        """Циклическая зависимость не приводит к зависанию."""
        code, out, _err = run_test_mode("A: B\nB: A\n", max_depth=50)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("цикл", out)

    def test_unknown_root(self) -> None:
        """Пакет, которого нет в тестовом репозитории, даёт код 3."""
        code, _out, err = run_test_mode("A: B\n", package_name="Z")
        self.assertEqual(code, EXIT_REPOSITORY_ERROR)
        self.assertIn("не найден в тестовом репозитории", err)

    def test_invalid_file_line(self) -> None:
        """Некорректная строка файла даёт код 3 и номер строки."""
        code, _out, err = run_test_mode("A: B\nbad line\n")
        self.assertEqual(code, EXIT_REPOSITORY_ERROR)
        self.assertIn("строка 2", err)


class RemoteModeTests(unittest.TestCase):
    """Проверка работы в режиме remote (сеть заменена заглушкой)."""

    def test_includes_transitive_dependencies(self) -> None:
        """Транзитивные зависимости NuGet попадают в граф и порядок."""
        data = {
            "Sample.Package": [("Lib.One", "1.2.0")],
            "Lib.One": [("Lib.Two", "2.0.0")],
            "Lib.Two": [],
        }

        def fake_fetch(_url: str, name: str, _version: str) -> list:
            """Заменяет сетевой запрос данными из словаря."""
            return data[name]

        with temp_dir() as directory:
            path = write_config(directory)
            with mock.patch(NUGET_TARGET, side_effect=fake_fetch):
                code, out, err = run_main([path, "--order"])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("  1. Lib.Two 2.0.0", out)
        self.assertIn("  3. Sample.Package 1.2.3", out)
        self.assertIn('n2: "Lib.Two 2.0.0"', out)

    def test_reports_repository_error(self) -> None:
        """Ошибка репозитория даёт сообщение в stderr и код 3."""
        failure = RepositoryError("нет связи")
        with temp_dir() as directory:
            path = write_config(directory)
            with mock.patch(NUGET_TARGET, side_effect=failure):
                code, _out, err = run_main([path])
        self.assertEqual(code, EXIT_REPOSITORY_ERROR)
        self.assertIn("Ошибка репозитория: нет связи", err)


class ConfigErrorTests(unittest.TestCase):
    """Проверка сообщений об ошибках конфигурации."""

    def test_reports_config_error(self) -> None:
        """Ошибка конфигурации даёт сообщение в stderr и код 2."""
        code, out, err = run_main(["missing.toml"])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertEqual(out, "")
        self.assertIn("Ошибка конфигурации", err)


if __name__ == "__main__":
    unittest.main()
