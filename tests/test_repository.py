"""Тесты источников данных: тестовый файл и NuGet."""

import unittest
from unittest import mock

from depviz.config import Config
from depviz.errors import RepositoryError
from depviz.repository import (
    FileRepository,
    NugetRepository,
    create_repository,
    load_test_graph,
    root_version,
)
from tests.helpers import temp_dir


def load(text: str) -> dict[str, list[str]]:
    """Загружает граф из текста файла."""
    with temp_dir() as directory:
        path = directory / "repo.txt"
        path.write_text(text, encoding="utf-8")
        return load_test_graph(str(path))


class TestFileTests(unittest.TestCase):
    """Проверка формата файла тестового репозитория."""

    def test_parse_graph(self) -> None:
        """Граф разбирается, комментарии и пустые строки игнорируются."""
        graph = load("# схема\nA: B C\n\nB: C\nC:\n")
        self.assertEqual(graph, {"A": ["B", "C"], "B": ["C"], "C": []})

    def test_commas_are_allowed(self) -> None:
        """Зависимости можно разделять запятыми."""
        self.assertEqual(load("A: B, C\n"), {"A": ["B", "C"]})

    def test_rejects_lowercase_names(self) -> None:
        """Имена не из больших латинских букв отклоняются."""
        with self.assertRaises(RepositoryError) as context:
            load("A: b\n")
        self.assertIn("строка 1", str(context.exception))

    def test_rejects_missing_colon(self) -> None:
        """Строка без двоеточия отклоняется."""
        with self.assertRaises(RepositoryError):
            load("A B\n")

    def test_rejects_duplicate_definition(self) -> None:
        """Повторное описание пакета отклоняется."""
        with self.assertRaises(RepositoryError) as context:
            load("A: B\nA: C\n")
        self.assertIn("дважды", str(context.exception))

    def test_unreadable_file(self) -> None:
        """Отсутствующий файл вызывает RepositoryError."""
        with self.assertRaises(RepositoryError):
            load_test_graph("no/such/file.txt")


class FileRepositoryTests(unittest.TestCase):
    """Проверка тестового репозитория."""

    def test_dependencies(self) -> None:
        """Возвращаются зависимости без версий."""
        repository = FileRepository({"A": ["B"]})
        self.assertEqual(repository.dependencies("A", ""), [("B", "")])

    def test_leaf_without_definition(self) -> None:
        """Пакет, упомянутый только как зависимость, не имеет зависимостей."""
        repository = FileRepository({"A": ["B"]})
        self.assertEqual(repository.dependencies("B", ""), [])

    def test_unknown_package(self) -> None:
        """Неизвестный пакет вызывает ошибку."""
        repository = FileRepository({"A": ["B"]})
        with self.assertRaises(RepositoryError) as context:
            repository.dependencies("Z", "")
        self.assertIn("Z", str(context.exception))


class NugetRepositoryTests(unittest.TestCase):
    """Проверка кэширования запросов к NuGet."""

    def test_cache(self) -> None:
        """Повторный запрос того же пакета не обращается к сети."""
        target = "depviz.repository.get_direct_dependencies"
        with mock.patch(target, return_value=[("B", "1.0.0")]) as fetch:
            repository = NugetRepository("http://host/")
            first = repository.dependencies("A", "1.0.0")
            second = repository.dependencies("a", "1.0.0")
        self.assertEqual(first, second)
        self.assertEqual(fetch.call_count, 1)


class FactoryTests(unittest.TestCase):
    """Проверка выбора репозитория по конфигурации."""

    def test_create_repository_by_mode(self) -> None:
        """Режим test даёт файловый репозиторий, remote — NuGet."""
        with temp_dir() as directory:
            path = directory / "repo.txt"
            path.write_text("A: B\n", encoding="utf-8")
            test = Config("A", "1.0.0", str(path), "test", "g.svg", 2)
            self.assertIsInstance(create_repository(test), FileRepository)
            self.assertEqual(root_version(test), "")

    def test_create_nuget_repository(self) -> None:
        """Режим remote даёт репозиторий NuGet и сохраняет версию."""
        remote = Config("A", "1.0.0", "http://h/", "remote", "g.svg", 2)
        self.assertIsInstance(create_repository(remote), NugetRepository)
        self.assertEqual(root_version(remote), "1.0.0")


if __name__ == "__main__":
    unittest.main()
