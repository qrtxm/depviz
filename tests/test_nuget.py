"""Тесты получения зависимостей NuGet."""

import json
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

from depviz.errors import RepositoryError
from depviz.nuget import (
    build_nuspec_url,
    build_versions_url,
    fetch_nuspec,
    fetch_versions,
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


def publish_versions(
    directory: Path, name: str, versions: list[str]
) -> None:
    """Создаёт индекс версий NuGet для тестового пакета."""
    package_dir = directory / name.lower()
    package_dir.mkdir(parents=True, exist_ok=True)
    index = package_dir / "index.json"
    index.write_text(json.dumps({"versions": versions}), encoding="utf-8")


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
        """Простая версия задаёт включительную нижнюю границу."""
        self.assertEqual(
            resolve_version("1.2.0", ["1.2.0", "1.3.0"]), "1.2.0"
        )
        self.assertEqual(
            resolve_version("1.2.0", ["1.2.1", "1.3.0"]), "1.2.1"
        )

    def test_resolve_ranges(self) -> None:
        """Выбирается минимальная опубликованная версия внутри диапазона."""
        versions = ["1.0.0", "1.0.1", "1.5.0", "2.0.0", "3.0.0", "4.1.0"]
        self.assertEqual(
            resolve_version("[1.0, 2.0)", versions), "1.0.0"
        )
        self.assertEqual(resolve_version("[4.1.0]", versions), "4.1.0")
        self.assertEqual(resolve_version("(1.0,)", versions), "1.0.1")
        self.assertEqual(resolve_version("(,2.0]", versions), "1.0.0")

    def test_prerelease_version_order(self) -> None:
        """Стабильная версия новее prerelease той же версии."""
        versions = ["1.0.0", "1.0.0-rc.2", "1.0.0-beta.1"]
        self.assertEqual(
            resolve_version("[1.0.0-beta.1,)", versions), "1.0.0-beta.1"
        )

    def test_resolve_bad_range(self) -> None:
        """Пустые, незакрытые и обратные диапазоны вызывают ошибку."""
        for text in ("", "  ", "[1.0", "(,)", "[2.0,1.0]"):
            with self.subTest(text=text):
                with self.assertRaises(RepositoryError):
                    resolve_version(text, ["1.0.0", "2.0.0"])

    def test_no_version_satisfies_range(self) -> None:
        """Пустое пересечение диапазона с версиями репозитория — ошибка."""
        with self.assertRaises(RepositoryError):
            resolve_version("[2.0, 3.0)", ["1.0.0", "3.0.0"])


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
        self.assertEqual(
            build_versions_url("https://host/v3/", "Newtonsoft.Json"),
            "https://host/v3/newtonsoft.json/index.json",
        )

    def test_fetch_versions(self) -> None:
        """Список версий читается из index.json."""
        with temp_dir() as directory:
            publish_versions(directory, "Sample.Package", ["1.0.0", "2.0.0"])
            self.assertEqual(
                fetch_versions(directory.as_uri(), "Sample.Package"),
                ["1.0.0", "2.0.0"],
            )

    def test_fetch_and_extract(self) -> None:
        """Прямые зависимости разрешаются по индексам доступных версий."""
        with temp_dir() as directory:
            url = publish(
                directory, "Sample.Package", "1.0.0", NUSPEC_TEMPLATE
            )
            publish_versions(directory, "Lib.One", ["1.2.0", "1.3.0"])
            publish_versions(directory, "Lib.Three", ["4.1.0"])
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
