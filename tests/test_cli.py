"""Тесты интерфейса командной строки."""

import contextlib
import io
import unittest

from depviz.cli import EXIT_CONFIG_ERROR, EXIT_OK, main
from tests.helpers import temp_dir, write_config


def run_main(argv: list[str]) -> tuple[int, str, str]:
    """Запускает main и возвращает код выхода, stdout и stderr."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    """Проверка поведения командной строки."""

    def test_prints_parameters(self) -> None:
        """Приложение выводит все параметры в формате ключ-значение."""
        with temp_dir() as directory:
            code, out, err = run_main([write_config(directory)])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("package_name = 'Sample.Package'", out)
        self.assertIn("max_depth = 3", out)

    def test_reports_config_error(self) -> None:
        """Ошибка конфигурации даёт сообщение в stderr и код 2."""
        code, out, err = run_main(["missing.toml"])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertEqual(out, "")
        self.assertIn("Ошибка конфигурации", err)


if __name__ == "__main__":
    unittest.main()
