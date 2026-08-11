import unittest

from query_parser import (
    MAX_QUERY_LIST_VALUES,
    QueryValidationError,
    python_query_to_filters,
    python_query_to_mongo,
)


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

    def test_membership_requires_a_list_or_tuple(self):
        with self.assertRaisesRegex(
            QueryValidationError,
            "right side of 'in' must be a list or tuple",
        ):
            python_query_to_filters("var in 'density'")

    def test_field_types_are_validated(self):
        with self.assertRaisesRegex(
            QueryValidationError,
            "min requires a numeric value",
        ):
            python_query_to_filters("min > 'zero'")
        with self.assertRaisesRegex(
            QueryValidationError,
            "Ordered comparisons are not supported for variable_name",
        ):
            python_query_to_filters("var > 'density'")
        with self.assertRaisesRegex(
            QueryValidationError,
            "contains.*text fields",
        ):
            python_query_to_filters("contains(min, '1')")

    def test_membership_and_query_complexity_are_bounded(self):
        values = ", ".join(str(value) for value in range(MAX_QUERY_LIST_VALUES + 1))
        with self.assertRaisesRegex(
            QueryValidationError,
            "Membership lists are limited",
        ):
            python_query_to_filters(f"min in [{values}]")

    def test_syntax_errors_are_normalized(self):
        with self.assertRaisesRegex(QueryValidationError, "Invalid query syntax"):
            python_query_to_filters("var ==")


if __name__ == "__main__":
    unittest.main()
