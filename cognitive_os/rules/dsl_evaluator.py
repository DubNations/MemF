from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(slots=True)
class EvalResult:
    ok: bool
    value: bool
    error: Optional[str] = None


_ALLOWED_NODES = {
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.In,
    ast.NotIn,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Subscript,
    ast.Index,
    ast.Attribute,
}
_ALLOWED_ROOT_NAMES = {"goal", "boundary", "knowledge_count", "metadata"}


def evaluate_condition(expression: str, env: Dict[str, Any]) -> EvalResult:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        return EvalResult(ok=False, value=False, error=f"syntax_error:{exc.msg}")

    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            return EvalResult(ok=False, value=False, error=f"unsupported_node:{type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in _ALLOWED_ROOT_NAMES:
            return EvalResult(ok=False, value=False, error=f"unknown_name:{node.id}")

    try:
        compiled = compile(tree, "<dsl>", "eval")
        value = eval(compiled, {"__builtins__": {}}, env)
        return EvalResult(ok=True, value=bool(value))
    except Exception as exc:  # defensive
        return EvalResult(ok=False, value=False, error=f"eval_error:{exc}")
