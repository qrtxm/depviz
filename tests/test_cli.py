"""Тесты интерфейса командной строки."""

import contextlib
import io
import unittest
from unittest import mock

from depviz.cli import (
    EXIT_CONFIG_ERROR,
    EXIT_OK,
    EXIT_REPOSITORY_ERROR,
    main,
)
from depviz.errors import RepositoryError
from tests.helpers import temp_dir, write_config

NUGET_TARGET = "depviz.repository.get_direct_dependencies"


def run_main(argv: list[str]) -> tuple[int, str, str]:
    """Запускает main и возвращает код выхода, stdout и stderr."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def run_test_mode(text: str, **overrides: object) -> tuple[int, str, str]:
    """Запускает приложение в тестовом режиме с графом из текста."""
    with temp_dir() as directory:
        repo = directory / "repo.txt"
        repo.write_text(text, encoding="utf-8")
        path = write_config(
            directory,
            package_name=overrides.pop("package_name", "A"),
            repository=str(repo).replace("\\", "/"),
            repository_mode="test",
            **overrides,
        )
        return run_main([path])


class TestModeTests(unittest.TestCase):
    """Проверка работы приложения с тестовым репозиторием."""

    def test_prints_graph(self) -> None:
        """Граф тестового репозитория строится и выводится."""
        code, out, err = run_test_mode("A: B C\nB: D\nC: D\n", max_depth=5)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("  A -> B, C", out)
        self.assertIn("  D (нет зависимостей)", out)

    def test_depth_is_respected(self) -> None:
        """Максимальная глубина из конфигурации ограничивает анализ."""
        _code, out, _err = run_test_mode("A: B\nB: C\n", max_depth=1)
        self.assertNotIn("C", out.replace("циклы", ""))
        self.assertIn("B (глубина анализа исчерпана)", out)

    def test_cycle_is_reported(self) -> None:
        """Циклическая зависимость не приводит к зависанию и выводится."""
        code, out, _err = run_test_mode("A: B\nB: A\n", max_depth=50)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("  A -> B -> A", out)

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

    def test_builds_transitive_graph(self) -> None:
        """Транзитивные зависимости NuGet попадают в граф."""
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
                code, out, err = run_main([path])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("Sample.Package 1.2.3 -> Lib.One 1.2.0", out)
        self.assertIn("Lib.One 1.2.0 -> Lib.Two 2.0.0", out)

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
