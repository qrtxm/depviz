"""Тесты загрузки и проверки конфигурации."""

import unittest

from depviz.config import Config, format_parameters, load_config
from depviz.errors import ConfigError
from tests.helpers import temp_dir, write_config


class LoadConfigTests(unittest.TestCase):
    """Проверка корректных конфигураций."""

    def test_valid_remote_config(self) -> None:
        """Корректный конфигурационный файл читается без ошибок."""
        with temp_dir() as directory:
            config = load_config(write_config(directory))
        self.assertEqual(config.package_name, "Sample.Package")
        self.assertEqual(config.package_version, "1.2.3")
        self.assertEqual(config.repository_mode, "remote")
        self.assertEqual(config.max_depth, 3)

    def test_valid_test_config(self) -> None:
        """В тестовом режиме проверяется существование файла графа."""
        with temp_dir() as directory:
            repo = directory / "repo.txt"
            repo.write_text("A: B\n", encoding="utf-8")
            path = write_config(
                directory,
                package_name="A",
                repository=str(repo).replace("\\", "/"),
                repository_mode="test",
            )
            config = load_config(path)
        self.assertEqual(config.package_name, "A")

    def test_format_parameters_lists_every_key(self) -> None:
        """Вывод параметров содержит все ключи в формате ключ-значение."""
        config = Config("A", "1.0.0", "x", "test", "g.svg", 2)
        lines = format_parameters(config)
        self.assertEqual(len(lines), len(config.__dataclass_fields__))
        self.assertIn("max_depth = 2", lines)


class ConfigErrorTests(unittest.TestCase):
    """Проверка обработки ошибок для каждого параметра."""

    def assert_rejected(self, text: str, **overrides: object) -> None:
        """Проверяет, что конфигурация отклоняется, и текст ошибки."""
        with temp_dir() as directory:
            path = write_config(directory, **overrides)
            with self.assertRaises(ConfigError) as context:
                load_config(path)
        self.assertIn(text, str(context.exception))

    def test_missing_file(self) -> None:
        """Отсутствующий файл конфигурации даёт понятную ошибку."""
        with self.assertRaises(ConfigError) as context:
            load_config("no/such/config.toml")
        self.assertIn("не найден", str(context.exception))

    def test_broken_toml(self) -> None:
        """Некорректный синтаксис TOML отклоняется."""
        with temp_dir() as directory:
            path = directory / "config.toml"
            path.write_text("package_name = = 1", encoding="utf-8")
            with self.assertRaises(ConfigError) as context:
                load_config(str(path))
        self.assertIn("некорректный TOML", str(context.exception))

    def test_missing_parameter(self) -> None:
        """Отсутствие параметра называется в сообщении."""
        with temp_dir() as directory:
            path = directory / "config.toml"
            path.write_text('package_name = "A"\n', encoding="utf-8")
            with self.assertRaises(ConfigError) as context:
                load_config(str(path))
        self.assertIn("max_depth", str(context.exception))

    def test_unknown_parameter(self) -> None:
        """Неизвестный параметр отклоняется."""
        self.assert_rejected("неизвестные параметры", extra="1")

    def test_empty_name(self) -> None:
        """Пустое имя пакета отклоняется."""
        self.assert_rejected("не должен быть пустым", package_name="  ")

    def test_bad_name(self) -> None:
        """Недопустимые символы в имени пакета отклоняются."""
        self.assert_rejected("package_name", package_name="bad name!")

    def test_test_mode_requires_capital_letters(self) -> None:
        """В тестовом режиме имя пакета состоит из больших букв."""
        self.assert_rejected(
            "большие латинские буквы",
            package_name="abc",
            repository_mode="test",
        )

    def test_bad_version(self) -> None:
        """Строка, не являющаяся версией, отклоняется."""
        self.assert_rejected("package_version", package_version="latest")

    def test_bad_url(self) -> None:
        """Репозиторий в режиме remote должен быть http(s)-адресом."""
        self.assert_rejected("не является URL", repository="ftp://host/")

    def test_missing_test_repository(self) -> None:
        """Несуществующий файл тестового репозитория отклоняется."""
        self.assert_rejected(
            "не найден",
            package_name="A",
            repository="missing.txt",
            repository_mode="test",
        )

    def test_bad_mode(self) -> None:
        """Неизвестный режим работы отклоняется."""
        self.assert_rejected("repository_mode", repository_mode="local")

    def test_bad_output_extension(self) -> None:
        """Файл изображения обязан иметь расширение .svg."""
        self.assert_rejected(".svg", output_file="graph.png")

    def test_depth_must_be_integer(self) -> None:
        """Глубина, заданная строкой, отклоняется."""
        self.assert_rejected("целым числом", max_depth="3")

    def test_depth_out_of_range(self) -> None:
        """Глубина вне допустимых границ отклоняется."""
        self.assert_rejected("max_depth должен быть", max_depth=0)
        self.assert_rejected("max_depth должен быть", max_depth=1000)

    def test_boolean_is_not_depth(self) -> None:
        """Булево значение не принимается за целое число."""
        self.assert_rejected("целым числом", max_depth=True)


if __name__ == "__main__":
    unittest.main()
