import unittest

from embed_context.catalog import load_catalog
from embed_context.query import QueryError, Searcher, load_query_config, lookup_code, read, tokenize
from embed_context.yamlio import YamlError

from tests.helpers import REPOSITORY, CatalogTestCase


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
