import ast
from typing import Any, Dict, List, Optional

FIELD_ALIASES = {
    "var": "variable_name",
    "type": "variable_type",
    "dataset": "source_dataset",
    "source": "source_dataset",
    "min": "min",
    "max": "max",
}

ALLOWED_FIELDS = {
    "variable_name",
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
