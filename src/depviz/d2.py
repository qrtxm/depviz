"""Представление графа на языке диаграмм D2 и получение изображения SVG."""

import subprocess
from collections.abc import Sequence
from pathlib import Path

from depviz.errors import RenderError
from depviz.graph import DependencyGraph

D2_COMMAND = ("d2",)
D2_SUFFIX = ".d2"
RENDER_TIMEOUT_SECONDS = 120
ROOT_FILL = "#cfe8ff"
CYCLE_COLOR = "#cc3333"
CYCLE_LABEL = "цикл"
UNEXPANDED_COLOR = "#888888"
DASH_STYLE = "3"
INDENT = "  "


def to_d2(graph: DependencyGraph) -> str:
    """Преобразует граф зависимостей в текст на языке D2."""
    ids = {key: f"n{index}" for index, key in enumerate(graph.names)}
    back_edges = {(cycle[-2], cycle[-1]) for cycle in graph.cycles}
    lines = ["direction: down"]
    for key, node_id in ids.items():
        lines.extend(_node_lines(graph, key, node_id))
    for source, targets in graph.edges.items():
        for target in targets:
            is_back = (source, target) in back_edges
            lines.extend(_edge_lines(ids[source], ids[target], is_back))
    return "\n".join(lines) + "\n"


def d2_path_for(svg_path: str) -> Path:
    """Возвращает путь файла D2, лежащего рядом с изображением."""
    return Path(svg_path).with_suffix(D2_SUFFIX)


def write_d2(text: str, svg_path: str) -> Path:
    """Сохраняет текст D2 рядом с изображением и возвращает путь к нему."""
    path = d2_path_for(svg_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as error:
        raise RenderError(f"не удалось записать {path}: {error}") from None
    return path


def render_svg(
    d2_path: Path, svg_path: str, command: Sequence[str] = D2_COMMAND
) -> None:
    """Строит изображение SVG из файла D2 программой d2."""
    arguments = [*command, str(d2_path), svg_path]
    try:
        completed = subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            timeout=RENDER_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        raise RenderError(
            f"программа {command[0]!r} не найдена: установите D2 "
            "(https://d2lang.com) и добавьте её в PATH"
        ) from None
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RenderError(f"не удалось запустить d2: {error}") from None
    if completed.returncode:
        details = completed.stderr.strip() or completed.stdout.strip()
        raise RenderError(f"d2 завершился с ошибкой: {details}")


def _quote(text: str) -> str:
    """Оформляет текст как строку D2 в двойных кавычках."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + escaped.replace("\n", " ") + '"'


def _node_lines(graph: DependencyGraph, key: str, node_id: str) -> list[str]:
    """Возвращает описание вершины: подпись и оформление."""
    styles = []
    if key == graph.root:
        styles.append(f'style.fill: "{ROOT_FILL}"')
    if key in graph.unexpanded:
        styles.append(f'style.stroke: "{UNEXPANDED_COLOR}"')
        styles.append(f"style.stroke-dash: {DASH_STYLE}")
    head = f"{node_id}: {_quote(graph.label(key))}"
    if not styles:
        return [head]
    return [head + " {", *[INDENT + style for style in styles], "}"]


def _edge_lines(source: str, target: str, is_back: bool) -> list[str]:
    """Возвращает описание ребра; ребро, замыкающее цикл, выделяется."""
    if not is_back:
        return [f"{source} -> {target}"]
    return [
        f"{source} -> {target}: {_quote(CYCLE_LABEL)} {{",
        f'{INDENT}style.stroke: "{CYCLE_COLOR}"',
        f'{INDENT}style.font-color: "{CYCLE_COLOR}"',
        "}",
    ]
