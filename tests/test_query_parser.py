import unittest

from query_parser import python_query_to_filters, python_query_to_mongo


class QueryParserTests(unittest.TestCase):
    def test_aliases_and_source_clause_are_split_for_catalog_queries(self):
        query_filter, source_filters = python_query_to_filters(
            "var == 'density' and source(producer == 'alpha')"
        )

        self.assertEqual(query_filter, {"variable_name": "density"})
        self.assertEqual(source_filters, [{"producer": "alpha"}])

    def test_contains_escapes_literal_search_text(self):
        self.assertEqual(
            python_query_to_mongo("contains(dataset, 'run[1]')"),
            {"source_dataset": {"$regex": "run\\[1\\]"}},
        )

    def test_source_clause_inside_or_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "source.*top-level 'and' clause",
        ):
            python_query_to_filters("var == 'density' or source(producer == 'alpha')")

    def test_unknown_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown/unsupported field"):
            python_query_to_filters("unknown_field == 1")


if __name__ == "__main__":
    unittest.main()
