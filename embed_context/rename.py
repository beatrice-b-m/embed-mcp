"""Rename a document or an entry, and every link to it.

A document's ID is its file name, and other documents link to it by that ID,
so a rename touches the file name and every link value that names it. This
module changes exactly those things and nothing else:

- it edits only the character spans of link values (and, for an entry, of its
  key), so comments, layout, and prose are untouched even where prose happens
  to contain the old name;
- it matches whole IDs, so renaming `image` leaves `internal-v2.image.x` and
  the word "image" alone;
- it rewrites every form a link takes: a full address, `#entry` within a
  document, and the bare keys of local link types;
- it reloads the catalog afterwards and restores every file if the result
  does not check cleanly or has lost a link.

Plain-text values that equal the old name exactly are not links, so they are
listed for the maintainer to check by hand: for an entry, text fields of its
document such as a qualifier naming a column; for a document, values in every
YAML and JSON file of the repository, such as a retrieval case or the legacy ID
map.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .catalog import ID_PATTERN, Catalog, Node, load_catalog
from .yamlio import YamlDocument, YamlError, read_yaml


class RenameError(ValueError):
    """A rename that cannot be made, or that was undone because it failed."""


@dataclass(frozen=True)
class Edit:
    file: Path
    start: int
    end: int
    old: str
    new: str
    line: int


@dataclass
class RenamePlan:
    old: str
    new: str
    edits: list[Edit] = field(default_factory=list)
    move: tuple[Path, Path] | None = None
    links: int = 0
    unchanged: list[tuple[Path, int, str]] = field(default_factory=list)  # (file, line, text) to check by hand


def plan_rename(catalog: Catalog, old: str, new: str) -> RenamePlan:
    """Work out every edit a rename needs, without writing anything."""
    if catalog.errors:
        raise RenameError(f"the catalog has {len(catalog.errors)} errors; fix them first (run `embed-context check`)")
    node = catalog.nodes.get(old)
    if node is None:
        matches = difflib.get_close_matches(old, list(catalog.nodes), n=1, cutoff=0.6)
        hint = f"; did you mean `{matches[0]}`?" if matches else ""
        raise RenameError(f"unknown ID `{old}`{hint}")
    document = old.split("#", 1)[0]
    if node.parent is None:
        if "#" in new or not ID_PATTERN.match(new):
            raise RenameError(f"`{new}` is not a valid document ID; use lowercase letters, digits, `.`, `-`, and `_`")
        target = node.source.file.with_name(f"{new}.yaml")
        if target.exists():
            raise RenameError(f"{_relative(catalog, target)} already exists")
    else:
        parent = old.rsplit("/", 1)[0] if "/" in old.split("#", 1)[1] else document
        separator = "/" if parent != document else "#"
        if "#" not in new:
            new = f"{parent}{separator}{new}"  # a bare key renames the entry in place
        key = new[len(parent) + 1 :] if new.startswith(parent + separator) else ""
        if not key or "#" in key or "/" in key:
            raise RenameError(f"`{new}` must rename only the last part of `{old}`, for example `{parent}{separator}<new key>`")
    if new == old:
        raise RenameError("the new name is the old name")
    if new in catalog.nodes:
        raise RenameError(f"`{new}` already exists")

    plan = RenamePlan(old, new)
    texts: dict[Path, str] = {}
    edited: set[tuple[Path, tuple]] = set()
    for link in catalog.links:
        if not _names(link.target, old):
            continue
        source = catalog.nodes[link.source].source
        span = source.spans.get(link.value_path)
        if span is None:  # every link value is a scalar the reader recorded
            raise RenameError(f"cannot locate the link at {_relative(catalog, link.file)}:{link.line}")
        text = texts.setdefault(link.file, link.file.read_text(encoding="utf-8"))
        written, quote = _unquote(text[span[0] : span[1]])
        rewritten = _rewrite(written, link.target, old, new, document)
        plan.links += 1
        if rewritten != written:
            plan.edits.append(Edit(link.file, span[0], span[1], text[span[0] : span[1]], f"{quote}{rewritten}{quote}", link.line))
            edited.add((link.file, link.value_path))

    if node.parent is None:
        plan.move = (node.source.file, node.source.file.with_name(f"{new}.yaml"))
    else:
        span = node.source.key_spans[node.path]
        text = texts.setdefault(node.source.file, node.source.file.read_text(encoding="utf-8"))
        written, quote = _unquote(text[span[0] : span[1]])
        plan.edits.append(Edit(node.source.file, span[0], span[1], text[span[0] : span[1]], f"{quote}{new.rsplit(separator, 1)[1]}{quote}", node.source.line(node.path)))

    plan.unchanged = _plain_mentions(catalog, node, old, edited)
    return plan


def apply_rename(catalog: Catalog, plan: RenamePlan) -> Catalog:
    """Write a planned rename, then reload and check the catalog. Every file
    is restored if the result has errors or has lost a link."""
    originals: dict[Path, str] = {}
    for edit in plan.edits:
        originals.setdefault(edit.file, edit.file.read_text(encoding="utf-8"))
    moved = False
    try:
        for file, original in originals.items():
            text = original
            for edit in sorted((e for e in plan.edits if e.file == file), key=lambda e: e.start, reverse=True):
                text = text[: edit.start] + edit.new + text[edit.end :]
            file.write_text(text, encoding="utf-8")
        if plan.move:
            plan.move[0].rename(plan.move[1])
            moved = True
        result = load_catalog(catalog.root)
        problems = [finding.format(catalog.root) for finding in result.errors]
        if not problems and (plan.new not in result.nodes or plan.old in result.nodes or len(result.links) != len(catalog.links)):
            problems.append("the renamed catalog does not have the same links")
        if problems:
            raise RenameError("the rename was undone because the result does not check cleanly:\n  " + "\n  ".join(problems[:10]))
        return result
    except BaseException:
        if moved:
            plan.move[1].rename(plan.move[0])
        for file, original in originals.items():
            file.write_text(original, encoding="utf-8")
        raise


def _names(target: str, old: str) -> bool:
    """Whether a resolved link target is ``old`` or lies inside it."""
    return target == old or target.startswith(old + "#") or target.startswith(old + "/")


def _rewrite(written: str, target: str, old: str, new: str, document: str) -> str:
    """The new text of a link value that currently reads ``written``."""
    if written.startswith(old) and _names(written, old):
        return new + written[len(old) :]  # a full address
    if "#" not in old:
        return written  # a document rename leaves the document's links to its own entries alone
    relative, new_relative = old[len(document) :], new[len(document) :]  # "#key", "#new-key"
    if written.startswith(relative) and _names(written, relative):
        return new_relative + written[len(relative) :]
    if written.startswith(relative[1:]) and _names(written, relative[1:]):
        return new_relative[1:] + written[len(relative) - 1 :]  # a local link type's bare key
    raise RenameError(f"cannot rewrite the link `{written}` to `{target}`")


def _plain_mentions(catalog: Catalog, node: Node, old: str, edited: set[tuple[Path, tuple]]) -> list[tuple[Path, int, str]]:
    """Text values equal to the old name that are not links. For an entry,
    only its own document is searched, since qualifiers name columns of their
    own table; for a document, every YAML file outside hidden directories."""
    names = {old} if node.parent is None else {old, old.rsplit("#", 1)[1].rsplit("/", 1)[-1]}
    found = []
    if node.parent is None:
        visible = [p for p in catalog.root.rglob("*") if p.is_file() and not any(part.startswith(".") for part in p.relative_to(catalog.root).parts)]
        files = [p for p in visible if p.suffix == ".yaml"]
        for file in sorted(p for p in visible if p.suffix == ".json"):
            found.extend((file, 0, f"{where}: {value}") for where, value in _json_strings(file) if value in names)
    else:
        files = [node.source.file]
    for file in sorted(files):
        try:
            doc = read_yaml(file)
        except YamlError:
            continue
        for path, (start, _) in doc.spans.items():
            if (file, path) in edited or path == node.path:
                continue
            value = _value_at(doc, path)
            if isinstance(value, str) and value in names:
                found.append((file, doc.line(path), f"{_where(path)}: {value}"))
    return found


def _json_strings(file: Path) -> list[tuple[str, str]]:
    """Every string key and value in a JSON file, with where it is."""
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return []
    found: list[tuple[str, str]] = []

    def walk(value: Any, where: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                found.append((where or "(key)", key))
                walk(child, f"{where}.{key}" if where else key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{where}[{index}]")
        elif isinstance(value, str):
            found.append((where, value))

    walk(data, "")
    return found


def _value_at(doc: YamlDocument, path: tuple) -> Any:
    value = doc.data
    for part in path:
        try:
            value = value[part]
        except (KeyError, IndexError, TypeError):
            return None
    return value


def _unquote(text: str) -> tuple[str, str]:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1], text[0]
    return text, ""


def _where(path: tuple) -> str:
    return ".".join(str(part) for part in path)


def _relative(catalog: Catalog, file: Path) -> str:
    try:
        return str(file.relative_to(catalog.root))
    except ValueError:
        return str(file)
