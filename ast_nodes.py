from dataclasses import dataclass, field
from typing import List, Tuple, Any


class Node: pass


@dataclass
class Program(Node):
    statements: List[Any] = field(default_factory=list)


@dataclass
class Assignment(Node):
    name: str
    value: Any
    line: int = 0


@dataclass
class ExprStatement(Node):
    expr: Any
    line: int = 0


@dataclass
class FnDef(Node):
    name: str
    params: List[str]
    body: Any          # Pipeline
    line: int = 0


@dataclass
class Pipeline(Node):
    source: Any
    stages: List['StageCall'] = field(default_factory=list)


@dataclass
class StageCall(Node):
    name: str
    args: List[Any]    # qualquer expressão
    line: int = 0


# ─── expressões ────────────────────────────────────────────

@dataclass
class ImplicitField(Node):
    """`.field` — campo do argumento implícito do estágio."""
    field: str
    line: int = 0


@dataclass
class FieldAccess(Node):
    """`expr.field` — acesso explícito (usado em predicados compostos)."""
    obj: Any
    field: str
    line: int = 0


@dataclass
class BinaryOp(Node):
    op: str
    left: Any
    right: Any
    line: int = 0


@dataclass
class UnaryOp(Node):
    op: str
    operand: Any
    line: int = 0


@dataclass
class Call(Node):
    """Chamada de função em contexto de expressão (não-estágio)."""
    name: str
    args: List[Any]
    line: int = 0


@dataclass
class Identifier(Node):
    name: str
    line: int = 0


@dataclass
class NumberLit(Node):
    value: Any
    line: int = 0


@dataclass
class StringLit(Node):
    value: str
    line: int = 0


@dataclass
class BoolLit(Node):
    value: bool
    line: int = 0


@dataclass
class ListLit(Node):
    items: List[Any]


@dataclass
class DictLit(Node):
    pairs: List[Tuple[str, Any]]