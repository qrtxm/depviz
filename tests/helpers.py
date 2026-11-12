"""Вспомогательные функции для тестов."""

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_VALUES = {
    "package_name": "Sample.Package",
    "package_version": "1.2.3",
    "repository": "https://example.org/v3-flatcontainer/",
    "repository_mode": "remote",
    "output_file": "graph.svg",
    "max_depth": 3,
}


def render_toml(values: dict[str, object]) -> str:
    """Преобразует словарь параметров в текст TOML."""
    lines = []
    for key, value in values.items():
        if isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        else:
            lines.append(f"{key} = {str(value).lower()}")
    return "\n".join(lines) + "\n"


@contextmanager
def temp_dir() -> Iterator[Path]:
    """Создаёт временный каталог и удаляет его после использования."""
    with tempfile.TemporaryDirectory() as name:
        yield Path(name)


def write_config(directory: Path, **overrides: object) -> str:
    """Записывает config.toml с параметрами по умолчанию и переопределениями.

    Значения из overrides заменяют соответствующие значения по умолчанию.
    """
    output = (directory / "graph.svg").as_posix()
    values = {**DEFAULT_VALUES, "output_file": output, **overrides}
    path = directory / "config.toml"
    path.write_text(render_toml(values), encoding="utf-8")
    return str(path)
