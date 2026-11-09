"""Получение прямых зависимостей пакета NuGet из репозитория."""

import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from depviz.errors import RepositoryError

REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "depviz/0.1"
MIN_VERSION_PARTS = 3
MAX_VERSION_PARTS = 4
ZERO_PART = "0"
RANGE_OPENERS = "[("
RANGE_CLOSERS = "])"
RANGE_SEPARATOR = ","


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


def resolve_version(version_range: str) -> str:
    """Выбирает версию по диапазону NuGet: нижняя граница диапазона.

    Менеджер NuGet при восстановлении берёт минимальную версию,
    удовлетворяющую диапазону, поэтому «1.0» означает «не ниже 1.0»,
    а для «[1.0, 2.0)» выбирается 1.0.
    """
    text = version_range.strip()
    if not text:
        raise RepositoryError("у зависимости не указана версия")
    if text[0] not in RANGE_OPENERS:
        return text
    if text[-1] not in RANGE_CLOSERS:
        raise RepositoryError(f"некорректный диапазон версий: {text!r}")
    bounds = [part.strip() for part in text[1:-1].split(RANGE_SEPARATOR)]
    chosen = next((bound for bound in bounds if bound), "")
    if not chosen:
        raise RepositoryError(f"некорректный диапазон версий: {text!r}")
    return chosen


def build_nuspec_url(base_url: str, name: str, version: str) -> str:
    """Строит URL файла .nuspec в «плоском контейнере» NuGet."""
    package_id = quote(name.lower(), safe="")
    package_version = quote(normalize_version(version), safe="")
    return (
        f"{base_url.rstrip('/')}/{package_id}/{package_version}/"
        f"{package_id}.nuspec"
    )


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


def parse_dependencies(nuspec_text: str) -> list[Dependency]:
    """Извлекает прямые зависимости из текста .nuspec.

    Зависимости всех групп целевых платформ объединяются; повторы
    (без учёта регистра имени) отбрасываются.
    """
    try:
        root = ElementTree.fromstring(nuspec_text)
    except ElementTree.ParseError as error:
        raise RepositoryError(f"некорректный .nuspec: {error}") from None
    found: dict[str, Dependency] = {}
    for element in root.iter():
        if _local_name(element.tag) != "dependency":
            continue
        name = element.get("id", "").strip()
        if not name:
            raise RepositoryError("в .nuspec есть зависимость без id")
        found.setdefault(
            name.lower(), Dependency(name, element.get("version", ""))
        )
    return list(found.values())


def get_direct_dependencies(
    base_url: str, name: str, version: str
) -> list[tuple[str, str]]:
    """Возвращает прямые зависимости пакета как пары (имя, версия)."""
    nuspec = fetch_nuspec(base_url, name, version)
    result = []
    for dependency in parse_dependencies(nuspec):
        resolved = resolve_version(dependency.version_range)
        result.append((dependency.name, resolved))
    return result


def _local_name(tag: str) -> str:
    """Возвращает имя XML-элемента без пространства имён."""
    return tag.rpartition("}")[2]
