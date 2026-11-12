"""Получение прямых зависимостей пакета NuGet из репозитория."""

import json
import re
import xml.etree.ElementTree
from dataclasses import dataclass
from functools import cmp_to_key
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from depviz.errors import RepositoryError

xml_element = xml.etree.ElementTree.Element
xml_parse_error = xml.etree.ElementTree.ParseError

REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "depviz/0.1"
MIN_VERSION_PARTS = 3
MAX_VERSION_PARTS = 4
ZERO_PART = "0"
RANGE_OPENERS = "[("
RANGE_CLOSERS = "])"
RANGE_SEPARATOR = ","
FRAMEWORK_OTHER = 0
FRAMEWORK_KINDS = (
    (3, "net"),
    (2, "netcoreapp"),
    (1, "netstandard"),
)
VERSION_PATTERN = re.compile(
    r"\d+(?:\.\d+){0,3}(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"
)


@dataclass(frozen=True)
class Dependency:
    """Прямая зависимость: имя пакета и диапазон допустимых версий."""

    name: str
    version_range: str


def normalize_version(version: str) -> str:
    """Приводит версию к нормализованному виду NuGet (в нижнем регистре)."""
    main, separator, suffix = version.strip().lower().partition("-")
    main = main.partition("+")[0]
    suffix = suffix.partition("+")[0]
    parts = [str(int(part)) for part in main.split(".")]
    while len(parts) < MIN_VERSION_PARTS:
        parts.append(ZERO_PART)
    if len(parts) == MAX_VERSION_PARTS and parts[-1] == ZERO_PART:
        parts.pop()
    return ".".join(parts) + separator + suffix


def _parse_version_range(
    version_range: str,
) -> tuple[str, bool, str, bool]:
    """Разбирает диапазон: нижняя/верхняя границы и их включительность."""
    text = version_range.strip()
    if not text:
        raise RepositoryError("у зависимости не указана версия")
    if text[0] not in RANGE_OPENERS:
        if VERSION_PATTERN.fullmatch(text):
            return text, True, "", False
        raise RepositoryError(f"некорректная версия зависимости: {text!r}")
    if text[-1] not in RANGE_CLOSERS:
        raise RepositoryError(f"некорректный диапазон версий: {text!r}")
    bounds = text[1:-1].split(RANGE_SEPARATOR)
    if len(bounds) == 1:
        return _parse_exact_range(text, bounds[0].strip())
    return _parse_interval_range(text, bounds)


def _parse_exact_range(
    text: str, version: str
) -> tuple[str, bool, str, bool]:
    """Проверяет диапазон с единственной точной версией [x]."""
    if text[0] == "[" and text[-1] == "]" and version:
        if VERSION_PATTERN.fullmatch(version):
            return version, True, version, True
    raise RepositoryError(f"некорректный диапазон версий: {text!r}")


def _validate_range_bound(bound: str, label: str) -> None:
    """Проверяет формат одной границы диапазона, если она задана."""
    if bound and not VERSION_PATTERN.fullmatch(bound):
        raise RepositoryError(f"некорректная {label}: {bound!r}")


def _parse_interval_range(
    text: str, bounds: list[str]
) -> tuple[str, bool, str, bool]:
    """Разбирает диапазон с двумя границами, одна может быть пустой."""
    if len(bounds) != 2:
        raise RepositoryError(f"некорректный диапазон версий: {text!r}")
    lower, upper = (bound.strip() for bound in bounds)
    if not lower and not upper:
        raise RepositoryError(f"некорректный диапазон версий: {text!r}")
    _validate_range_bound(lower, "нижняя граница")
    _validate_range_bound(upper, "верхняя граница")
    if lower and upper and _compare_versions(lower, upper) > 0:
        raise RepositoryError(f"обратный диапазон версий: {text!r}")
    return lower, text[0] == "[", upper, text[-1] == "]"

def _version_key_parts(
    version: str,
) -> tuple[tuple[int, ...], tuple[str, ...]]:
    """Разделяет версию на числовую часть и идентификаторы prerelease."""
    text = version.strip().lower().split("+", maxsplit=1)[0]
    main, separator, suffix = text.partition("-")
    numbers = tuple(int(part) for part in main.split("."))
    numbers += (0,) * (MAX_VERSION_PARTS - len(numbers))
    prerelease = tuple(suffix.split(".")) if separator else ()
    return numbers, prerelease


def _compare_prerelease_part(first: str, second: str) -> int:
    """Сравнивает два prerelease-идентификатора SemVer."""
    first_numeric = first.isdigit()
    second_numeric = second.isdigit()
    if first_numeric and second_numeric:
        return (int(first) > int(second)) - (int(first) < int(second))
    if first_numeric != second_numeric:
        return -1 if first_numeric else 1
    return (first > second) - (first < second)


def _compare_prerelease(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    """Сравнивает последовательности prerelease-идентификаторов."""
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for first, second in zip(left, right):
        result = _compare_prerelease_part(first, second)
        if result:
            return result
    return (len(left) > len(right)) - (len(left) < len(right))

def _compare_versions(left: str, right: str) -> int:
    """Сравнивает две версии NuGet без учёта build metadata."""
    left_numbers, left_pre = _version_key_parts(left)
    right_numbers, right_pre = _version_key_parts(right)
    if left_numbers != right_numbers:
        return (left_numbers > right_numbers) - (left_numbers < right_numbers)
    return _compare_prerelease(left_pre, right_pre)


def _matches_range(
    version: str, bounds: tuple[str, bool, str, bool]
) -> bool:
    """Проверяет, входит ли доступная версия в заданный диапазон."""
    lower, include_lower, upper, include_upper = bounds
    if lower:
        comparison = _compare_versions(version, lower)
        if comparison < 0 or (comparison == 0 and not include_lower):
            return False
    if upper:
        comparison = _compare_versions(version, upper)
        if comparison > 0 or (comparison == 0 and not include_upper):
            return False
    return True


def resolve_version(
    version_range: str, available_versions: list[str] | None = None
) -> str:
    """Выбирает минимальную доступную версию, удовлетворяющую диапазону."""
    bounds = _parse_version_range(version_range)
    lower, include_lower, upper, include_upper = bounds
    if available_versions is None:
        if lower and include_lower and upper == lower and include_upper:
            return lower
        raise RepositoryError(
            f"для диапазона {version_range!r} нужен список версий пакета"
        )
    matching = [
        version
        for version in available_versions
        if _matches_range(version, bounds)
    ]
    if not matching:
        raise RepositoryError(
            f"в репозитории нет версии, подходящей под диапазон "
            f"{version_range!r}"
        )
    return min(matching, key=cmp_to_key(_compare_versions))


def build_nuspec_url(base_url: str, name: str, version: str) -> str:
    """Строит URL файла .nuspec в «плоском контейнере» NuGet."""
    package_id = quote(name.lower(), safe="")
    package_version = quote(normalize_version(version), safe="")
    return (
        f"{base_url.rstrip('/')}/{package_id}/{package_version}/"
        f"{package_id}.nuspec"
    )


def build_versions_url(base_url: str, name: str) -> str:
    """Строит URL индекса доступных версий пакета NuGet."""
    package_id = quote(name.lower(), safe="")
    return f"{base_url.rstrip('/')}/{package_id}/index.json"


def fetch_versions(base_url: str, name: str) -> list[str]:
    """Получает список опубликованных версий из flat container index.json."""
    url = build_versions_url(base_url, name)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8-sig"))
    except HTTPError as error:
        raise RepositoryError(
            f"список версий пакета {name} не получен из {url} "
            f"(HTTP {error.code})"
        ) from None
    except (
        URLError,
        TimeoutError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        message = f"ошибка чтения списка версий {url}: {error}"
        raise RepositoryError(message) from None
    versions = data.get("versions") if isinstance(data, dict) else None
    if not isinstance(versions, list) or not all(
        isinstance(version, str) for version in versions
    ):
        raise RepositoryError(f"некорректный индекс версий пакета: {url}")
    return versions


def fetch_nuspec(base_url: str, name: str, version: str) -> str:
    """Скачивает .nuspec пакета указанной версии и возвращает его текст."""
    try:
        url = build_nuspec_url(base_url, name, version)
    except ValueError:
        raise RepositoryError(f"некорректная версия: {version!r}") from None
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8-sig")
    except HTTPError as error:
        raise RepositoryError(
            f"пакет {name} {version} не получен из {url} "
            f"(HTTP {error.code})"
        ) from None
    except (URLError, TimeoutError, UnicodeDecodeError) as error:
        raise RepositoryError(f"ошибка доступа к {url}: {error}") from None


def _find_dependencies_container(
    root: xml_element,
) -> xml_element | None:
    """Находит контейнер прямых зависимостей в дереве .nuspec."""
    return next(
        (
            element
            for element in root.iter()
            if _local_name(element.tag) == "dependencies"
        ),
        None,
    )


def _parse_dependency_elements(
    source: xml_element,
) -> list[Dependency]:
    """Преобразует XML-элементы dependency в уникальные зависимости."""
    found: dict[str, Dependency] = {}
    for element in source:
        if _local_name(element.tag) != "dependency":
            continue
        name = element.get("id", "").strip()
        if not name:
            raise RepositoryError("в .nuspec есть зависимость без id")
        found.setdefault(
            name.lower(), Dependency(name, element.get("version", ""))
        )
    return list(found.values())


def parse_dependencies(nuspec_text: str) -> list[Dependency]:
    """Извлекает прямые зависимости из текста .nuspec.

    Если зависимости разбиты на группы по целевым платформам, берётся
    группа самой современной платформы (см. framework_rank). Повторы
    (без учёта регистра имени) отбрасываются.
    """
    try:
        root = xml.etree.ElementTree.fromstring(nuspec_text)
    except xml_parse_error as error:
        raise RepositoryError(f"некорректный .nuspec: {error}") from None
    container = _find_dependencies_container(root)
    if container is None:
        return []
    groups = [
        element
        for element in container
        if _local_name(element.tag) == "group"
    ]
    source = _newest_group(groups) if groups else container
    return _parse_dependency_elements(source)


def framework_rank(target_framework: str) -> tuple[int, int, int]:
    """Оценивает «современность» целевой платформы: больше — новее.

    Порядок: net5.0 и новее, затем netcoreapp, затем netstandard, затем
    остальные (.NET Framework, нестандартные и без указания платформы).
    """
    name = target_framework.strip().lower().lstrip(".")
    for kind, prefix in FRAMEWORK_KINDS:
        match = re.match(rf"{prefix}(\d+)\.(\d+)", name)
        if match:
            return (kind, int(match.group(1)), int(match.group(2)))
    return (FRAMEWORK_OTHER, 0, 0)


def _newest_group(groups: list[xml_element]) -> xml_element:
    """Выбирает группу новейшей платформы (при равенстве — последнюю)."""
    ranked = [
        (framework_rank(group.get("targetFramework", "")), index)
        for index, group in enumerate(groups)
    ]
    return groups[max(ranked)[1]]


def get_direct_dependencies(
    base_url: str, name: str, version: str
) -> list[tuple[str, str]]:
    """Возвращает прямые зависимости как пары (имя, минимальная версия)."""
    nuspec = fetch_nuspec(base_url, name, version)
    versions_cache: dict[str, list[str]] = {}
    result = []
    for dependency in parse_dependencies(nuspec):
        key = dependency.name.casefold()
        if key not in versions_cache:
            versions_cache[key] = fetch_versions(base_url, dependency.name)
        resolved = resolve_version(
            dependency.version_range, versions_cache[key]
        )
        result.append((dependency.name, resolved))
    return result


def _local_name(tag: str) -> str:
    """Возвращает имя XML-элемента без пространства имён."""
    return tag.rpartition("}")[2]
