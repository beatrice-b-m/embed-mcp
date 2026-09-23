"""Read catalog YAML files as plain data with line numbers.

Every scalar is read as a string; types come from the model, so values such
as ``N``, ``no``, ``1``, or ``6`` are never turned into booleans or numbers.
Anchors, aliases, explicit tags, and multi-document files are rejected so
that every file reads the same way to a human and to the engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import MarkedYAMLError
from ruamel.yaml.events import AliasEvent, DocumentStartEvent
from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode

# Plain (unquoted) scalars that YAML treats as null. They are rejected rather
# than read as text, because `field:` with nothing after it is almost always
# an unfinished edit.
_NULL_SPELLINGS = {"", "~", "null", "Null", "NULL"}

Path_ = tuple[str | int, ...]


class YamlError(Exception):
    def __init__(self, file: Path, line: int, message: str) -> None:
        super().__init__(f"{file}:{line}: {message}")
        self.file = file
        self.line = line
        self.message = message


@dataclass(frozen=True)
class YamlDocument:
    """The data of one file plus the line where each value starts."""

    file: Path
    data: Any
    lines: dict[Path_, int]

    def line(self, path: Path_) -> int:
        """Line of the value at ``path``, or of its nearest enclosing value."""
        while path not in self.lines and path:
            path = path[:-1]
        return self.lines.get(path, 1)


def read_yaml(file: Path) -> YamlDocument:
    return parse_yaml(file.read_text(encoding="utf-8"), file)


def parse_yaml(text: str, file: Path) -> YamlDocument:
    """Parse YAML text; ``file`` is used only in error messages."""
    yaml = YAML(typ="base", pure=True)
    try:
        _reject_unsupported_syntax(yaml, text, file)
        node = yaml.compose(text)
    except MarkedYAMLError as error:
        mark = error.problem_mark or error.context_mark
        raise YamlError(file, (mark.line + 1) if mark else 1, _describe(error)) from None
    lines: dict[Path_, int] = {}
    data = _convert(node, (), lines, file) if node is not None else {}
    return YamlDocument(file, data, lines)


def _reject_unsupported_syntax(yaml: YAML, text: str, file: Path) -> None:
    documents = 0
    for event in yaml.parse(text):
        line = event.start_mark.line + 1
        if isinstance(event, DocumentStartEvent):
            documents += 1
            if documents > 1:
                raise YamlError(file, line, "a file may hold only one document; remove the extra `---`")
        if isinstance(event, AliasEvent) or getattr(event, "anchor", None):
            raise YamlError(file, line, "anchors and aliases (`&name`, `*name`) are not supported; write the value out")
        tag = getattr(event, "tag", None)
        if tag is not None:
            raise YamlError(file, line, f"explicit tags such as `{tag}` are not supported; the model decides every type")


def _convert(node: Any, path: Path_, lines: dict[Path_, int], file: Path, line: int | None = None) -> Any:
    # A mapping value is located at its key's line, which is where a human
    # looks, even when the value itself starts on the next line.
    lines[path] = line if line is not None else node.start_mark.line + 1
    if isinstance(node, MappingNode):
        result: dict[str, Any] = {}
        for key_node, value_node in node.value:
            if not isinstance(key_node, ScalarNode):
                raise YamlError(file, key_node.start_mark.line + 1, "mapping keys must be plain text")
            key = key_node.value
            if key in result:
                raise YamlError(file, key_node.start_mark.line + 1, f"duplicate key `{key}`")
            result[key] = _convert(value_node, (*path, key), lines, file, key_node.start_mark.line + 1)
        return result
    if isinstance(node, SequenceNode):
        return [_convert(item, (*path, index), lines, file) for index, item in enumerate(node.value)]
    if node.style is None and node.value in _NULL_SPELLINGS:
        raise YamlError(
            file,
            lines[path],
            "empty value; give a value, remove the line, or quote it if you mean the text",
        )
    return node.value


def _describe(error: MarkedYAMLError) -> str:
    problem = error.problem or error.context or "invalid YAML"
    return f"invalid YAML: {problem}"
