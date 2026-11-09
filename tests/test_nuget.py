"""Тесты получения зависимостей NuGet."""

import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

from depviz.errors import RepositoryError
from depviz.nuget import (
    build_nuspec_url,
    fetch_nuspec,
    framework_rank,
    get_direct_dependencies,
    normalize_version,
    parse_dependencies,
    resolve_version,
)
from tests.helpers import temp_dir

NUSPEC_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">
  <metadata>
    <id>Sample.Package</id>
    <version>1.0.0</version>
    <dependencies>
      <group targetFramework=".NETStandard2.0">
        <dependency id="Lib.One" version="1.2.0" />
        <dependency id="Lib.Two" version="[2.0.0, 3.0.0)" />
      </group>
      <group targetFramework="net6.0">
        <dependency id="Lib.One" version="1.2.0" />
        <dependency id="lib.one" version="1.2.0" />
        <dependency id="Lib.Three" version="[4.1.0]" />
      </group>
      <group targetFramework=".NETFramework4.6.2">
        <dependency id="Lib.Old" version="1.0.0" />
      </group>
    </dependencies>
  </metadata>
</package>
"""

NUSPEC_WITHOUT_DEPENDENCIES = """<package><metadata><id>X</id></metadata>
</package>"""


def publish(directory: Path, name: str, version: str, text: str) -> str:
    """Кладёт .nuspec в структуру «плоского контейнера» и даёт file:// URL."""
    package_dir = directory / name.lower() / version
    package_dir.mkdir(parents=True)
    path = package_dir / f"{name.lower()}.nuspec"
    path.write_text(text, encoding="utf-8")
    return directory.as_uri()


class VersionTests(unittest.TestCase):
    """Проверка разбора версий и диапазонов."""

    def test_normalize_version(self) -> None:
        """Версия приводится к нормализованной форме NuGet."""
        self.assertEqual(normalize_version("1.0"), "1.0.0")
        self.assertEqual(normalize_version("1.0.0.0"), "1.0.0")
        self.assertEqual(normalize_version("1.2.3.4"), "1.2.3.4")
        self.assertEqual(normalize_version("01.2.3"), "1.2.3")
        self.assertEqual(
            normalize_version("1.0.0-Beta.1+Build"), "1.0.0-beta.1"
        )

    def test_resolve_plain_version(self) -> None:
        """Простая версия означает «не ниже» и берётся как есть."""
        self.assertEqual(resolve_version("1.2.0"), "1.2.0")

    def test_resolve_ranges(self) -> None:
        """Для диапазонов выбирается нижняя граница."""
        self.assertEqual(resolve_version("[1.0, 2.0)"), "1.0")
        self.assertEqual(resolve_version("[4.1.0]"), "4.1.0")
        self.assertEqual(resolve_version("(1.0,)"), "1.0")
        self.assertEqual(resolve_version("(,2.0]"), "2.0")

    def test_resolve_bad_range(self) -> None:
        """Пустой или незакрытый диапазон вызывает ошибку."""
        for text in ("", "  ", "[1.0", "(,)"):
            with self.subTest(text=text):
                with self.assertRaises(RepositoryError):
                    resolve_version(text)


class ParseTests(unittest.TestCase):
    """Проверка разбора .nuspec."""

    def test_newest_group_is_chosen(self) -> None:
        """Берётся группа новейшей платформы, повторы отбрасываются."""
        result = parse_dependencies(NUSPEC_TEMPLATE)
        names = [dependency.name for dependency in result]
        self.assertEqual(names, ["Lib.One", "Lib.Three"])
        self.assertEqual(result[1].version_range, "[4.1.0]")

    def test_dependencies_without_groups(self) -> None:
        """Зависимости вне групп (старый формат) читаются целиком."""
        text = (
            "<package><metadata><dependencies>"
            '<dependency id="A" version="1.0"/>'
            '<dependency id="B" version="2.0"/>'
            "</dependencies></metadata></package>"
        )
        names = [dependency.name for dependency in parse_dependencies(text)]
        self.assertEqual(names, ["A", "B"])

    def test_framework_rank_order(self) -> None:
        """Платформы упорядочены от новых к старым."""
        order = [
            "net8.0",
            "net6.0-windows",
            "netcoreapp3.1",
            ".NETStandard2.1",
            ".NETStandard2.0",
            ".NETFramework4.8",
        ]
        ranks = [framework_rank(name) for name in order]
        self.assertEqual(ranks, sorted(ranks, reverse=True))
        self.assertEqual(framework_rank(""), framework_rank("net462"))

    def test_equal_rank_takes_last_group(self) -> None:
        """Группы без различимой платформы: выбирается последняя."""
        text = (
            "<package><dependencies>"
            '<group targetFramework="uap10.0"><dependency id="A"'
            ' version="1.0"/></group>'
            '<group targetFramework="monoandroid"><dependency id="B"'
            ' version="1.0"/></group>'
            "</dependencies></package>"
        )
        names = [dependency.name for dependency in parse_dependencies(text)]
        self.assertEqual(names, ["B"])

    def test_no_dependencies(self) -> None:
        """Пакет без зависимостей даёт пустой список."""
        self.assertEqual(parse_dependencies(NUSPEC_WITHOUT_DEPENDENCIES), [])

    def test_broken_xml(self) -> None:
        """Некорректный XML вызывает RepositoryError."""
        with self.assertRaises(RepositoryError):
            parse_dependencies("<package>")

    def test_dependency_without_id(self) -> None:
        """Зависимость без id считается ошибкой."""
        with self.assertRaises(RepositoryError):
            parse_dependencies(
                "<package><dependencies><dependency version='1'/>"
                "</dependencies></package>"
            )


class FetchTests(unittest.TestCase):
    """Проверка получения данных из репозитория."""

    def test_build_url(self) -> None:
        """URL строится по схеме плоского контейнера NuGet."""
        url = build_nuspec_url("https://host/v3/", "Newtonsoft.Json", "13.0")
        self.assertEqual(
            url,
            "https://host/v3/newtonsoft.json/13.0.0/newtonsoft.json.nuspec",
        )

    def test_fetch_and_extract(self) -> None:
        """Прямые зависимости извлекаются по URL репозитория."""
        with temp_dir() as directory:
            url = publish(directory, "Sample.Package", "1.0.0", NUSPEC_TEMPLATE)
            result = get_direct_dependencies(url, "Sample.Package", "1.0")
        self.assertEqual(
            result, [("Lib.One", "1.2.0"), ("Lib.Three", "4.1.0")]
        )

    def test_missing_package(self) -> None:
        """Ответ HTTP 404 превращается в понятную ошибку о пакете."""
        failure = HTTPError("http://host/x", 404, "Not Found", None, None)
        with mock.patch("depviz.nuget.urlopen", side_effect=failure):
            with self.assertRaises(RepositoryError) as context:
                fetch_nuspec("http://host/", "Nope", "1.0.0")
        self.assertIn("Nope 1.0.0", str(context.exception))
        self.assertIn("404", str(context.exception))

    def test_missing_file_in_repository(self) -> None:
        """Отсутствие файла в репозитории даёт ошибку доступа."""
        with temp_dir() as directory:
            with self.assertRaises(RepositoryError) as context:
                fetch_nuspec(directory.as_uri(), "Nope", "1.0.0")
        self.assertIn("ошибка доступа", str(context.exception))

    def test_unreachable_repository(self) -> None:
        """Недоступный сервер даёт ошибку доступа."""
        with self.assertRaises(RepositoryError):
            fetch_nuspec("http://127.0.0.1:9/", "A", "1.0.0")

    def test_bad_version(self) -> None:
        """Версия, не приводимая к нормальной форме, даёт ошибку."""
        with self.assertRaises(RepositoryError):
            fetch_nuspec("http://127.0.0.1:9/", "A", "x.y")


if __name__ == "__main__":
    unittest.main()
