import ast
import re
from typing import Any, Dict, List, Optional, Tuple

FIELD_ALIASES = {
    "id": "variable_id",
    "var": "variable_name",
    "type": "variable_type",
    "dataset": "source_dataset",
    "source": "source_dataset",
    "min": "min",
    "max": "max",
}

ALLOWED_FIELDS = {
    "variable_name",
    "variable_id",
    "variable_type",
    "source_dataset",
    "producer",
    "casename",
    "file",
    "visualization_name",
    "visualization_kind",
    "visualization_source_dataset",
    "association_source",
    "variable_path",
    "campaign_path",
    "variable_location",
    "frame_index",
    "min",
    "max",
}


def _field_name(name: str) -> str:
    mapped = FIELD_ALIASES.get(name, name)
    if mapped not in ALLOWED_FIELDS:
        raise ValueError(f"Unknown/unsupported field: {name}")
    return mapped


def _const(node: ast.AST):
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _const(node.operand)
        if not isinstance(v, (int, float)):
            raise ValueError("Unary +/- is only allowed on numeric constants")
        return +v if isinstance(node.op, ast.UAdd) else -v

    if isinstance(node, (ast.List, ast.Tuple)):
        return [_const(elt) for elt in node.elts]

    raise ValueError(f"Only constants/lists are allowed, got: {type(node).__name__}")


def _compile_query_node(node: ast.AST) -> Dict[str, Any]:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "source":
        raise ValueError("source(...) is only supported as a top-level 'and' clause")

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "contains":
        if len(node.args) != 2 or node.keywords:
            raise ValueError("contains(...) takes exactly a field name and a search string")
        field_node, search_node = node.args
        if not isinstance(field_node, ast.Name):
            raise ValueError("contains(...) first argument must be a field name")
        search_text = _const(search_node)
        if not isinstance(search_text, str):
            raise ValueError("contains(...) search value must be a string")
        return {_field_name(field_node.id): {"$regex": re.escape(search_text)}}

    if isinstance(node, ast.BoolOp):
        op = "$and" if isinstance(node.op, ast.And) else "$or"
        parts = [_compile_query_node(v) for v in node.values]
        flat: List[Dict[str, Any]] = []
        for p in parts:
            if isinstance(p, dict) and op in p and len(p) == 1:
                flat.extend(p[op])
            else:
                flat.append(p)
        return {op: flat}

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = _compile_query_node(node.operand)
        return {"$nor": [inner]}

    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise ValueError("Chained comparisons are not supported")

        left = node.left
        op = node.ops[0]
        right = node.comparators[0]

        if not isinstance(left, ast.Name):
            raise ValueError("Left side must be a field name")

        field = _field_name(left.id)

        if isinstance(op, ast.Eq):
            return {field: _const(right)}
        if isinstance(op, ast.NotEq):
            return {field: {"$ne": _const(right)}}
        if isinstance(op, ast.In):
            return {field: {"$in": _const(right)}}
        if isinstance(op, ast.NotIn):
            return {field: {"$nin": _const(right)}}

        if isinstance(op, ast.Gt):
            return {field: {"$gt": _const(right)}}
        if isinstance(op, ast.GtE):
            return {field: {"$gte": _const(right)}}
        if isinstance(op, ast.Lt):
            return {field: {"$lt": _const(right)}}
        if isinstance(op, ast.LtE):
            return {field: {"$lte": _const(right)}}

        raise ValueError(f"Unsupported operator: {type(op).__name__}")

    if isinstance(node, ast.Name):
        field = _field_name(node.id)
        return {field: {"$ne": None}}

    raise ValueError(f"Unsupported expression: {type(node).__name__}")


def _combine_and(filters: List[Dict[str, Any]]) -> Dict[str, Any]:
    nonempty = [f for f in filters if f]
    if not nonempty:
        return {}
    if len(nonempty) == 1:
        return nonempty[0]
    return {"$and": nonempty}


def _is_source_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "source"


def _has_source_call(node: ast.AST) -> bool:
    return any(_is_source_call(child) for child in ast.walk(node))


def _top_level_and_terms(node: ast.AST) -> List[ast.AST]:
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        terms: List[ast.AST] = []
        for value in node.values:
            terms.extend(_top_level_and_terms(value))
        return terms
    return [node]


def python_query_to_mongo(expr: str) -> Dict[str, Any]:
    expr = (expr or "").strip()
    if not expr:
        return {}

    tree = ast.parse(expr, mode="eval")
    return _compile_query_node(tree.body)


def python_query_to_filters(expr: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    expr = (expr or "").strip()
    if not expr:
        return {}, []

    tree = ast.parse(expr, mode="eval")
    doc_filters: List[Dict[str, Any]] = []
    source_filters: List[Dict[str, Any]] = []

    for term in _top_level_and_terms(tree.body):
        if _is_source_call(term):
            if len(term.args) != 1 or term.keywords:
                raise ValueError("source(...) takes exactly one query expression")
            if _has_source_call(term.args[0]):
                raise ValueError("Nested source(...) clauses are not supported")
            source_filters.append(_compile_query_node(term.args[0]))
            continue

        if _has_source_call(term):
            raise ValueError("source(...) is only supported as a top-level 'and' clause")

        doc_filters.append(_compile_query_node(term))

    return _combine_and(doc_filters), source_filters


def and_filter(base: Dict[str, Any], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not extra:
        return base
    return {"$and": [base, extra]}


def _value_matches(value: Any, condition: Any) -> bool:
    if not isinstance(condition, dict):
        return value == condition

    for op, expected in condition.items():
        if op == "$ne":
            if value == expected:
                return False
            continue

        if op in {"$in", "$nin"}:
            try:
                matched = value in expected
            except TypeError:
                matched = False
            if op == "$in" and not matched:
                return False
            if op == "$nin" and matched:
                return False
            continue

        if op == "$regex":
            if not isinstance(value, str):
                return False
            return re.search(str(expected), value) is not None

        try:
            if op == "$gt" and not (value > expected):
                return False
            if op == "$gte" and not (value >= expected):
                return False
            if op == "$lt" and not (value < expected):
                return False
            if op == "$lte" and not (value <= expected):
                return False
        except TypeError:
            return False

        if op not in {"$gt", "$gte", "$lt", "$lte"}:
            raise ValueError(f"Unsupported filter operator: {op}")

    return True


def mongo_filter_matches(filter_doc: Dict[str, Any], values: Dict[str, Any]) -> bool:
    if not filter_doc:
        return True

    for key, condition in filter_doc.items():
        if key == "$and":
            return all(mongo_filter_matches(part, values) for part in condition)
        if key == "$or":
            return any(mongo_filter_matches(part, values) for part in condition)
        if key == "$nor":
            return not any(mongo_filter_matches(part, values) for part in condition)
        if key.startswith("$"):
            raise ValueError(f"Unsupported filter operator: {key}")

        if not _value_matches(values.get(key), condition):
            return False

    return True
