from ast_nodes import *
from lexer import FlowError


class NameError_(FlowError):
    def kind(self): return "Name"


BUILTINS = {
    "print", "filter", "map", "unique", "sort", "len", "range", "sum",
    "min", "max", "enumerate", "zip", "str", "int", "float", "bool",
    "list", "set", "dict", "reversed", "abs", "round", "any", "all",
}


class NameResolver:
    def __init__(self):
        self.scopes = [set()]

    def push(self): self.scopes.append(set())
    def pop(self):  self.scopes.pop()
    def define(self, name): self.scopes[-1].add(name)
    def is_defined(self, name): return any(name in s for s in reversed(self.scopes))

    def resolve_program(self, prog: Program):
        self.scopes[0].update(BUILTINS)
        # Pré-pass: coleta nomes de funções (permite forward references)
        for stmt in prog.statements:
            if isinstance(stmt, FnDef):
                self.define(stmt.name)
        for stmt in prog.statements:
            self.resolve_stmt(stmt)

    def resolve_stmt(self, stmt):
        if isinstance(stmt, FnDef):
            self.push()
            for p in stmt.params:
                self.define(p)
            self.resolve_pipeline(stmt.body)
            self.pop()
        elif isinstance(stmt, Assignment):
            self.resolve_pipeline(stmt.value)
            self.define(stmt.name)
        elif isinstance(stmt, ExprStatement):
            self.resolve_pipeline(stmt.expr)

    def resolve_pipeline(self, pipe: Pipeline):
        self.resolve_node(pipe.source)
        for stage in pipe.stages:
            self.resolve_stage(stage)

    def resolve_node(self, node):
        if isinstance(node, Identifier):
            if not self.is_defined(node.name):
                raise NameError_(f"undefined name '{node.name}'", node.line)
        elif isinstance(node, Pipeline):
            self.resolve_pipeline(node)
        elif isinstance(node, ListLit):
            for item in node.items: self.resolve_pipeline(item)
        elif isinstance(node, DictLit):
            for _, v in node.pairs: self.resolve_pipeline(v)
        elif isinstance(node, BinaryOp):
            self.resolve_node(node.left); self.resolve_node(node.right)
        elif isinstance(node, UnaryOp):
            self.resolve_node(node.operand)
        elif isinstance(node, FieldAccess):
            self.resolve_node(node.obj)
        elif isinstance(node, ImplicitField):
            pass
        elif isinstance(node, Call):
            if not self.is_defined(node.name):
                raise NameError_(f"undefined function '{node.name}'", node.line)
            for a in node.args: self.resolve_node(a)

    def resolve_stage(self, stage: StageCall):
        if not self.is_defined(stage.name):
            raise NameError_(f"undefined function '{stage.name}'", stage.line)
        for arg in stage.args:
            self.resolve_node(arg)