from dataclasses import dataclass, field
from typing import List, Tuple, Any


class IRNode: pass


@dataclass
class IRProgram(IRNode):
    stmts: List[Any] = field(default_factory=list)


@dataclass
class IRFnDef(IRNode):
    name: str
    params: List[str]
    body: IRNode


@dataclass
class IRAssign(IRNode):
    name: str
    value: IRNode


@dataclass
class IRExprStmt(IRNode):
    expr: IRNode


@dataclass
class IRCall(IRNode):
    func: str
    args: List[IRNode]


@dataclass
class IRLambda(IRNode):
    param: str
    body: IRNode


@dataclass
class IRField(IRNode):
    obj: IRNode
    field: str


@dataclass
class IRVar(IRNode):
    name: str


@dataclass
class IRNum(IRNode):
    value: Any


@dataclass
class IRStr(IRNode):
    value: str


@dataclass
class IRBool(IRNode):
    value: bool


@dataclass
class IRBinOp(IRNode):
    op: str
    left: IRNode
    right: IRNode


@dataclass
class IRUnOp(IRNode):
    op: str
    operand: IRNode


@dataclass
class IRList(IRNode):
    items: List[IRNode]


@dataclass
class IRDict(IRNode):
    pairs: List[Tuple[str, IRNode]]