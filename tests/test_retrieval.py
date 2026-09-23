"""Run the retrieval evaluation in tests/retrieval_cases.yaml against the real catalog."""

import unittest
from pathlib import Path

from embed_context.catalog import load_catalog
from embed_context.query import Searcher
from embed_context.yamlio import read_yaml

from tests.helpers import REPOSITORY

CASES = read_yaml(Path(__file__).with_name("retrieval_cases.yaml")).data["cases"]


def run_case(searchers: dict[tuple[str, ...], Searcher], case: dict) -> tuple[list[str], list[str]]:
    """The ranked IDs for a case, and a list of its failures."""
    modules = tuple(case.get("modules", []))
    if modules not in searchers:
        searchers[modules] = Searcher(load_catalog(REPOSITORY, list(modules) or None))
    ranked = [result["id"] for result in searchers[modules].search(case["query"], limit=20)["results"]]
    failures = []
    for expectation in case.get("expect", []):
        within = int(expectation["within"])
        if expectation["id"] not in ranked[:within]:
            rank = ranked.index(expectation["id"]) + 1 if expectation["id"] in ranked else "absent"
            failures.append(f"{expectation['id']} expected within {within}, ranked {rank}")
    for first, second in case.get("before", []):
        if first in ranked and second in ranked and ranked.index(first) > ranked.index(second):
            failures.append(f"{first} ranked below {second}")
    return ranked, failures


class RetrievalTests(unittest.TestCase):
    def test_retrieval_cases(self):
        searchers: dict[tuple[str, ...], Searcher] = {}
        for name, case in CASES.items():
            with self.subTest(case=name):
                ranked, failures = run_case(searchers, case)
                self.assertEqual(failures, [], f"{case['query']!r} ranked: {ranked[:10]}")


if __name__ == "__main__":
    # `python -m tests.test_retrieval` prints every case's ranking, for tuning model/query.yaml.
    searchers: dict[tuple[str, ...], Searcher] = {}
    for name, case in CASES.items():
        ranked, failures = run_case(searchers, case)
        print(f"{'FAIL' if failures else 'ok  '} {name}: {case['query']}")
        for failure in failures:
            print(f"       {failure}")
        print(f"       top: {ranked[:8]}")
