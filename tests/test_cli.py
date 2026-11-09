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

TARGET = "depviz.cli.get_direct_dependencies"


def run_main(argv: list[str]) -> tuple[int, str, str]:
    """Запускает main и возвращает код выхода, stdout и stderr."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    """Проверка поведения командной строки."""

    def test_prints_direct_dependencies(self) -> None:
        """Приложение выводит все прямые зависимости пакета."""
        found = [("Lib.One", "1.2.0"), ("Lib.Two", "2.0.0")]
        with temp_dir() as directory, mock.patch(TARGET, return_value=found):
            code, out, err = run_main([write_config(directory)])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("Sample.Package 1.2.3", out)
        self.assertIn("  Lib.One 1.2.0", out)
        self.assertIn("  Lib.Two 2.0.0", out)

    def test_prints_marker_for_empty_list(self) -> None:
        """Для пакета без зависимостей выводится пометка «нет»."""
        with temp_dir() as directory, mock.patch(TARGET, return_value=[]):
            code, out, _err = run_main([write_config(directory)])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("(нет)", out)

    def test_reports_config_error(self) -> None:
        """Ошибка конфигурации даёт сообщение в stderr и код 2."""
        code, out, err = run_main(["missing.toml"])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertEqual(out, "")
        self.assertIn("Ошибка конфигурации", err)

    def test_reports_repository_error(self) -> None:
        """Ошибка репозитория даёт сообщение в stderr и код 3."""
        failure = RepositoryError("нет связи")
        with temp_dir() as directory, mock.patch(TARGET, side_effect=failure):
            code, _out, err = run_main([write_config(directory)])
        self.assertEqual(code, EXIT_REPOSITORY_ERROR)
        self.assertIn("Ошибка репозитория: нет связи", err)


if __name__ == "__main__":
    unittest.main()
