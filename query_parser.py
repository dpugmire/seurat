import ast
from typing import Any, Dict, List, Optional

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


def python_query_to_mongo(expr: str) -> Dict[str, Any]:
    expr = (expr or "").strip()
    if not expr:
        return {}

    tree = ast.parse(expr, mode="eval")

    def compile_node(node: ast.AST) -> Dict[str, Any]:
        if isinstance(node, ast.BoolOp):
            op = "$and" if isinstance(node.op, ast.And) else "$or"
            parts = [compile_node(v) for v in node.values]
            flat: List[Dict[str, Any]] = []
            for p in parts:
                if isinstance(p, dict) and op in p and len(p) == 1:
                    flat.extend(p[op])
                else:
                    flat.append(p)
            return {op: flat}

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            inner = compile_node(node.operand)
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

    return compile_node(tree.body)


def and_filter(base: Dict[str, Any], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not extra:
        return base
    return {"$and": [base, extra]}


SOURCE_FILTER_FIELDS = {
    "sourceName",
    "source_name",
    "source_dataset",
    "producer",
    "casename",
    "file",
    "min",
    "max",
}


def python_source_filter_matches(expr: str, values: Dict[str, Any]) -> bool:
    expr = (expr or "").strip()
    if not expr:
        return True

    tree = ast.parse(expr, mode="eval")

    def value_of(node: ast.AST):
        if isinstance(node, ast.Name):
            if node.id in {"None", "True", "False"}:
                return {"None": None, "True": True, "False": False}[node.id]
            if node.id not in SOURCE_FILTER_FIELDS:
                raise ValueError(f"Unknown/unsupported source field: {node.id}")
            if node.id == "source_name":
                return values.get("sourceName", "")
            return values.get(node.id)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = value_of(node.operand)
            if not isinstance(v, (int, float)):
                raise ValueError("Unary +/- is only allowed on numeric values")
            return +v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, (ast.List, ast.Tuple)):
            return [value_of(elt) for elt in node.elts]
        raise ValueError(f"Unsupported source filter value: {type(node).__name__}")

    def compare(left, op: ast.AST, right) -> bool:
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.In):
            try:
                return left in right
            except TypeError:
                return False
        if isinstance(op, ast.NotIn):
            try:
                return left not in right
            except TypeError:
                return True
        try:
            if isinstance(op, ast.Gt):
                return left > right
            if isinstance(op, ast.GtE):
                return left >= right
            if isinstance(op, ast.Lt):
                return left < right
            if isinstance(op, ast.LtE):
                return left <= right
        except TypeError:
            return False
        raise ValueError(f"Unsupported source filter operator: {type(op).__name__}")

    def eval_node(node: ast.AST) -> bool:
        if isinstance(node, ast.BoolOp):
            parts = [eval_node(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(parts)
            if isinstance(node.op, ast.Or):
                return any(parts)
            raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not eval_node(node.operand)
        if isinstance(node, ast.Compare):
            left = value_of(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = value_of(comparator)
                if not compare(left, op, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Name):
            return bool(value_of(node))
        raise ValueError(f"Unsupported source filter expression: {type(node).__name__}")

    return bool(eval_node(tree.body))
