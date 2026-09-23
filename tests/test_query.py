import unittest

from embed_context.catalog import load_catalog
from embed_context.query import QueryError, Searcher, load_query_config, lookup_code, read, tokenize
from embed_context.yamlio import YamlError

from embed_context.render import render_named

from tests.helpers import REPOSITORY, CatalogTestCase, facts_missing_from_text


class TokenizeTests(unittest.TestCase):
    def test_compounds_yield_joined_form_and_parts(self):
        self.assertEqual(tokenize("BI-RADS", frozenset()), ["bi-rad", "birad", "bi", "rads"])

    def test_plurals_fold_and_stopwords_drop(self):
        self.assertEqual(tokenize("the findings", frozenset({"the"})), ["finding"])


class SearchTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.write("catalog/base/topic.body.yaml", "kind: topic\nlabel: Body\n")
        self.write("catalog/base/topic.breast.yaml", "kind: topic\nlabel: Breast\nbroader: [topic.body]\n")
        self.write("catalog/base/density.yaml", "kind: note\nlabel: Breast density\nstatus: open\nabout: [topic.breast]\n")
        self.write("catalog/base/margin.yaml", "kind: note\nlabel: Tumor margin\nstatus: open\ntags: [density of the edge]\n")
        self.write("catalog/base/closed.yaml", "kind: note\nlabel: Closed density note\nstatus: closed\n")

    def search(self, text, **filters):
        return Searcher(self.load()).search(text, **filters)

    def ids(self, text, **filters):
        return [result["id"] for result in self.search(text, **filters)["results"]]

    def test_field_weights_rank_label_matches_above_other_fields(self):
        ranked = self.ids("density")
        self.assertLess(ranked.index("density"), ranked.index("margin"))  # label beats tags

    def test_boosts_reorder_results(self):
        self.assertEqual(self.ids("density")[0], "closed")

    def test_expansions_find_related_words(self):
        self.assertEqual(self.ids("tumour"), ["margin"])

    def test_unmatched_terms_are_reported(self):
        self.assertEqual(self.search("density xylophone")["unmatched_terms"], ["xylophone"])

    def test_topic_filter_includes_narrower_topics(self):
        ranked = self.ids("density", topics=["topic.body"])
        self.assertIn("density", ranked)
        self.assertNotIn("margin", ranked)
        self.assertNotIn("closed", ranked)

    def test_an_empty_filtered_search_reports_what_the_filters_excluded(self):
        data = self.search("tumor", kinds=["topic"])
        self.assertEqual((data["results"], data["excluded_by_filters"]), ([], 1))
        self.assertNotIn("excluded_by_filters", self.search("xylophone"))
        self.assertNotIn("excluded_by_filters", self.search("density", kinds=["note"]))

    def test_kind_filter_and_unknown_kind(self):
        self.assertEqual({r["kind"] for r in self.search("breast", kinds=["topic"])["results"]}, {"topic"})
        with self.assertRaises(QueryError) as raised:
            self.search("breast", kinds=["notes"])
        self.assertIn("did you mean `note`?", str(raised.exception))

    def test_results_list_configured_backlinks(self):
        result = next(r for r in self.search("breast")["results"] if r["id"] == "topic.breast")
        self.assertEqual(result["links"], [{"name": "notes", "links": [{"id": "density", "kind": "note", "label": "Breast density"}]}])

    def test_invalid_configuration_reports_its_line(self):
        self.write("model/query.yaml", self.read_query().replace("expansion_weight: 0.5", "expansion_weight: half"))
        with self.assertRaises(YamlError) as raised:
            load_query_config(self.load())
        self.assertIn("expected a number", raised.exception.message)
        self.assertEqual(raised.exception.line, 5)

    def read_query(self):
        return (self.root / "model" / "query.yaml").read_text()


class ReadTests(CatalogTestCase):
    def test_summarized_entries_show_only_listed_fields_and_no_backlinks(self):
        self.write("catalog/base/n.yaml", "kind: note\nlabel: N\nstatus: open\nitems:\n  a:\n    label: A\n    next: [b]\n  b:\n    label: B\n")
        data = read(self.load(), "n")
        item = data["sections"][0]["entries"][0]
        self.assertTrue(item["summary"])
        self.assertEqual([f["name"] for f in item["fields"]], ["label"])
        self.assertNotIn("links", item)
        self.assertNotIn("backlinks", item)


class FixtureCodeLookupTests(CatalogTestCase):
    """Code lookup on the fixture model, whose `codes:` settings name its own kinds."""

    def setUp(self):
        super().setUp()
        self.write("catalog/base/list.colors.yaml", """
            kind: codelist
            label: Colors
            terms: {R: red, G: green}
            """)
        self.write("catalog/base/list.shapes.yaml", """
            kind: codelist
            label: Shapes
            terms: {R: round, S: square}
            """)
        self.write("catalog/base/list.listed.yaml", """
            kind: codelist
            label: Listed
            parsing: listed
            terms: {A: first, B: second, "A;B": both}
            """)
        self.write("catalog/base/list.joined.yaml", """
            kind: codelist
            label: Joined
            parsing: joined
            terms: {A: first, B: second}
            """)
        self.write("catalog/base/measure.color.yaml", """
            kind: measure
            label: Color
            gaps:
              blank:
                representation: blank or dash
                represented_values: ["", "-"]
                meaning: not recorded
            """)
        self.write("catalog/base/measure.shape.yaml", "kind: measure\nlabel: Shape\n")
        self.write("catalog/base/sheet.yaml", """
            kind: sheet
            label: Sheet
            cells:
              kind_of:
                records: []
              value:
                readings:
                  x:
                    representation: X
                    meaning: crossed out
                    status: closed
                  yes-or-no:
                    representation: Y or N
                    represented_values: [Y, N]
                    meaning: answered
                    status: open
                    caveats: [Answers may be stale.]
                    measure: measure.shape
                  described:
                    representation: any other letter
                    meaning: unexplained
                records:
                  - {id: measure.color, status: open, list: list.colors, when_cell: kind_of, when_value: C}
                  - {id: measure.shape, status: open, list: list.shapes, when_cell: kind_of, when_value: S}
            """)

    def lookup(self, address, value):
        catalog = self.load()
        self.assertEqual(self.messages(catalog), [])
        return lookup_code(catalog, address, value)

    def test_each_code_list_result_carries_its_mapping_qualifiers(self):
        result = self.lookup("sheet#value", "R")
        self.assertEqual([(c["meaning"], c["mapping"]["feature"]) for c in result["codes"]], [("red", "measure.color"), ("round", "measure.shape")])
        self.assertEqual(result["codes"][0]["mapping"]["qualifiers"], {"status": "open", "when_cell": "kind_of", "when_value": "C"})
        self.assertEqual(result["legend"]["records.status"], {"open": "Still open."})

    def test_a_feature_uses_only_its_own_mappings(self):
        result = self.lookup("measure.shape", "R")
        self.assertEqual([c["vocabulary"] for c in result["codes"]], ["list.shapes"])

    def test_an_interpretation_matches_its_representation_or_a_listed_value(self):
        self.assertEqual([(i["id"], i["match"]) for i in self.lookup("sheet#value", "X")["interpretations"]], [("sheet#value/x", "exact")])
        result = self.lookup("sheet#value", "N")
        [listed] = result["interpretations"]
        self.assertEqual((listed["id"], listed["match"], listed["caveats"]), ("sheet#value/yes-or-no", "listed", ["Answers may be stale."]))
        self.assertEqual(result["legend"]["reading.status"], {"open": "Still open.", "closed": "Finished."})

    def test_an_interpretation_carries_the_mapping_of_the_feature_it_names(self):
        [listed] = self.lookup("sheet#value", "Y")["interpretations"]
        self.assertEqual([m["feature"] for m in listed["mappings"]], ["measure.shape"])
        self.assertEqual(listed["mappings"][0]["qualifiers"]["when_value"], "S")

    def test_the_columns_other_interpretations_are_listed(self):
        result = self.lookup("sheet#value", "Q")
        self.assertEqual(result["interpretations"], [])
        self.assertEqual([i["id"] for i in result["other_interpretations"]], ["sheet#value/x", "sheet#value/yes-or-no", "sheet#value/described"])
        self.assertNotIn("other_interpretations", self.lookup("list.colors", "Q"))

    def test_a_feature_leaves_out_interpretations_of_other_features(self):
        self.assertEqual([i["id"] for i in self.lookup("measure.color", "Q")["other_interpretations"]], ["sheet#value/x", "sheet#value/described"])
        self.assertEqual(self.lookup("measure.color", "Y")["interpretations"], [])
        self.assertEqual([i["id"] for i in self.lookup("measure.shape", "Y")["interpretations"]], ["sheet#value/yes-or-no"])

    def test_a_missing_state_matches_a_listed_value(self):
        self.assertEqual([(s["id"], s["match"]) for s in self.lookup("sheet#value", "")["missing_states"]], [("measure.color#blank", "listed")])
        self.assertEqual(self.lookup("sheet#value", "blank or dash")["missing_states"][0]["match"], "exact")
        self.assertEqual(self.lookup("measure.shape", "")["missing_states"], [])

    def test_a_delimited_value_is_split_and_each_part_looked_up(self):
        match = self.lookup("list.listed", "B ; a;;C")["codes"][0]
        self.assertEqual((match["match"], match["delimiter"], match["parsing"]), ("tokens", ";", "listed"))
        self.assertEqual(match["tokens"], [{"code": "B", "meaning": "second"}, {"code": "a", "meaning": None, "similar_codes": ["A"]}, {"code": "C", "meaning": None}])
        self.assertEqual(self.lookup("list.listed", "B;a")["legend"], {"codelist.parsing": {"listed": "Codes separated by semicolons."}})

    def test_a_delimited_value_that_is_a_code_is_not_split(self):
        self.assertEqual(self.lookup("list.listed", "A;B")["codes"][0]["meaning"], "both")

    def test_other_parsings_never_split(self):
        match = self.lookup("list.joined", "A;B")["codes"][0]
        self.assertEqual((match["match"], match["parsing"]), ("none", "joined"))
        self.assertNotIn("tokens", match)

    def test_delimited_parsing_must_name_a_parsing_value(self):
        self.write("model/query.yaml", (self.root / "model/query.yaml").read_text().replace("{listed:", "{listd:"))
        with self.assertRaises(YamlError) as raised:
            load_query_config(self.load())
        self.assertIn("`listd` is not a value of any `parsing` field", raised.exception.message)

    def test_text_carries_every_fact_of_a_lookup(self):
        lookups = [
            ("sheet#value", "R"), ("sheet#value", "S"), ("sheet#value", "N"), ("sheet#value", "-"), ("sheet#value", "Q"),
            ("list.colors", "r"), ("list.listed", "B;a;C"), ("list.joined", "A;B"),
        ]
        for address, value in lookups:
            with self.subTest(address=address, value=value):
                data = self.lookup(address, value)
                text = render_named(self.root, "_code", data)
                self.assertEqual(facts_missing_from_text(data, text), [])
        text = render_named(self.root, "_code", self.lookup("sheet#value", "R"))
        self.assertIn("R has a meaning in 2 code lists", text)


class CodeLookupTests(unittest.TestCase):
    """Properties of code lookup on the real catalog, without naming its content."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(REPOSITORY)
        cls.config = load_query_config(cls.catalog)
        names = cls.config.codes
        cls.mapping = next(
            link for link in cls.catalog.links if link.spec.name == names["column_vocabulary_link"]
        )

    def test_every_code_of_a_vocabulary_resolves_exactly(self):
        vocabulary = self.catalog.nodes[self.mapping.target]
        for code, meaning in vocabulary.data["codes"].items():
            result = lookup_code(self.catalog, vocabulary.address, code, self.config)
            self.assertEqual(result["codes"][0]["meaning"], meaning)

    def test_a_column_uses_its_mappings_vocabularies(self):
        vocabulary = self.catalog.nodes[self.mapping.target]
        code = next(iter(vocabulary.data["codes"]))
        result = lookup_code(self.catalog, self.mapping.source, code, self.config)
        self.assertIn(vocabulary.address, [match["vocabulary"] for match in result["codes"]])

    def test_an_unknown_value_is_reported_without_a_meaning(self):
        result = lookup_code(self.catalog, self.mapping.target, "no such code", self.config)
        self.assertEqual([match["match"] for match in result["codes"]], ["none"])
