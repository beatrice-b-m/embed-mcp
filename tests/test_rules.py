"""The cross-document rules in model/rules.yaml, on a small synthetic catalog
that uses the real model. The documents are placeholders, not catalog content."""

import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from embed_context.catalog import load_catalog
from embed_context.yamlio import YamlError

from tests.helpers import REPOSITORY

SEMANTIC = {
    "module.yaml": "kind: module\nlabel: Placeholder semantic\nmodule_type: semantic\n",
    "thing.yaml": "kind: clinical_object\nlabel: Thing\ndefinition: Placeholder.\ngrain: One thing.\n",
    "part.yaml": "kind: clinical_object\nlabel: Part\ndefinition: Placeholder.\ngrain: One part.\n",
    "thing-part.yaml": """
        kind: relationship
        label: Thing has part
        relationship_type: hierarchy
        definition: Placeholder.
        cardinality: {targets_per_source: zero_or_more, sources_per_target: exactly_one}
        optionality: {source: optional, target: required}
        source_object: thing
        target_object: part
        """,
}

TABLE = """
    kind: table
    label: {name}
    grain: One row.
    keys:
      id-key: {{key_type: technical, uniqueness: {uniqueness}, completeness: complete, columns: [id]}}
    columns:
      id: {{type: {id_type}, nullable: false}}
      parent_id: {{type: int64, nullable: true}}
    """

JOIN = """
    kind: join
    join_type: {join_type}
    source_completeness: {completeness}
    cardinality: {{targets_per_source: {forward}, sources_per_target: zero_or_more}}
    source_columns: [{source}]
    target_columns: [{target}]
    """


class RuleTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        shutil.copytree(REPOSITORY / "model", self.root / "model")
        shutil.copytree(REPOSITORY / "templates", self.root / "templates")
        for name, text in SEMANTIC.items():
            self.write(f"semantic/{name}", text)
        self.write("profile/module.yaml", "kind: module\nlabel: Placeholder profile\nmodule_type: profile\nrequires: [semantic]\n")
        self.table("p.a")
        self.table("p.b")
        self.join("p.join.b-a", source="p.b#parent_id", target="p.a#id")  # many b rows per a row: a valid one-to-many
        self.join("p.join.a-b", source="p.a#id", target="p.b#parent_id", forward="zero_or_more", completeness="required", join_type="reference")
        self.write(
            "profile/p.path.yaml",
            "kind: join_path\ndefinition: Placeholder.\nrelationship: thing-part\njoins: [p.join.a-b, p.join.b-a]\n",
        )

    def tearDown(self):
        self._temporary.cleanup()

    def write(self, relative, text):
        path = self.root / "catalog" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")

    def table(self, name, uniqueness="unique", id_type="int64"):
        self.write(f"profile/{name}.yaml", TABLE.format(name=name, uniqueness=uniqueness, id_type=id_type))

    def join(self, name, source, target, forward="zero_or_one", completeness="optional", join_type="hierarchy"):
        self.write(f"profile/{name}.yaml", JOIN.format(source=source, target=target, forward=forward, completeness=completeness, join_type=join_type))

    def errors(self):
        return [f"{f.file.name}: {f.message}" for f in load_catalog(self.root).errors]

    def assertBreaks(self, fragment):
        errors = self.errors()
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_the_valid_catalog_has_no_findings(self):
        self.assertEqual(self.errors(), [])

    def test_at_most_one_target_needs_a_unique_target_key(self):
        self.table("p.a", uniqueness="not_unique")
        self.assertBreaks("p.join.b-a.yaml: targets_per_source is zero_or_one, but (id) is not declared as a unique key of p.a")

    def test_at_least_one_target_needs_required_source_columns(self):
        self.join("p.join.b-a", source="p.b#parent_id", target="p.a#id", forward="exactly_one")
        self.assertBreaks("targets_per_source is exactly_one, so every source row needs the join columns")

    def test_paired_columns_have_the_same_type(self):
        self.table("p.a", id_type="string")
        self.assertBreaks("`p.b#parent_id` is int64 but `p.a#id` is string")

    def test_column_lists_have_the_same_length(self):
        self.join("p.join.b-a", source="p.b#parent_id, p.b#id", target="p.a#id")
        self.assertBreaks("2 source columns but 1 target columns")

    def test_one_side_of_a_join_is_one_table(self):
        self.join("p.join.b-a", source="p.b#parent_id, p.a#id", target="p.a#id, p.b#id")
        self.assertBreaks("belong to several tables")

    def test_source_completeness_agrees_with_a_key_on_the_same_columns(self):
        self.join("p.join.a-b", source="p.a#id", target="p.b#parent_id", forward="zero_or_more", completeness="optional", join_type="reference")
        self.assertBreaks("source_completeness is optional, but key `p.a#id-key` on the same columns is complete")

    def test_keys_on_the_same_columns_agree(self):
        self.write("profile/p.a.yaml", TABLE.format(name="p.a", uniqueness="unique", id_type="int64").replace(
            "      id-key:", "      id-again: {key_type: technical, uniqueness: not_unique, completeness: complete, columns: [id]}\n      id-key:"))
        self.assertBreaks("has the same columns as `p.a#id-again` but a different uniqueness")

    def test_hierarchy_joins_form_no_cycle(self):
        self.join("p.join.a-b", source="p.a#id", target="p.b#parent_id", forward="zero_or_more", completeness="required", join_type="hierarchy")
        self.assertBreaks("hierarchy joins form a cycle")

    def test_consecutive_joins_in_a_path_meet(self):
        self.write("profile/p.path.yaml", "kind: join_path\ndefinition: Placeholder.\nrelationship: thing-part\njoins: [p.join.b-a, p.join.b-a]\n")
        self.assertBreaks("`p.join.b-a` ends at p.a but `p.join.b-a` starts at p.b")

    def test_a_rules_file_naming_an_unknown_field_fails_with_its_line(self):
        path = self.root / "model" / "rules.yaml"
        path.write_text(path.read_text().replace("uniqueness: uniqueness", "uniqueness: uniqeness"))
        with self.assertRaises(YamlError) as raised:
            load_catalog(self.root)
        self.assertIn("`key` has no field `uniqeness`", raised.exception.message)
        self.assertIn("rules.yaml:", str(raised.exception))
