"""AST tipada → IR.

A transformação central continua sendo uma linha: `a |> f(args)` vira
`f(args, a)`. A novidade é que agora `args` pode ser uma expressão com
`.field` — nesse caso ela é envolvida em `lambda _x: <expr>` (o `_x`
substitui `.`). Escopos aninhados sombreiam `_x` naturalmente, o que dá
o comportamento correto para pipelines aninhadas sem trabalho extra.
"""
from ast_nodes import *
from ir import *
from type_checker import has_implicit


BUILTIN_PYTHON = {
    "print": "print", "filter": "filter", "map": "map",
    "unique": "set", "sort": "sorted",
    "len": "len", "range": "range", "sum": "sum",
    "min": "min", "max": "max",
    "enumerate": "enumerate", "zip": "zip",
    "str": "str", "int": "int", "float": "float", "bool": "bool",
    "list": "list", "set": "set", "dict": "dict",
    "reversed": "reversed", "abs": "abs", "round": "round",
    "any": "any", "all": "all",
}

LAMBDA_PARAM = "_x"
OP_PYTHON = {"and": "and", "or": "or", "not": "not"}


class IRBuilder:
    def build_program(self, prog: Program) -> IRProgram:
        return IRProgram(stmts=[self.build_stmt(s) for s in prog.statements])

    def build_stmt(self, s):
        if isinstance(s, FnDef):
            return IRFnDef(name=s.name, params=s.params,
                           body=self.build_pipeline(s.body))
        if isinstance(s, Assignment):
            return IRAssign(name=s.name, value=self.build_pipeline(s.value))
        if isinstance(s, ExprStatement):
            return IRExprStmt(expr=self.build_pipeline(s.expr))
        raise Exception(f"unknown statement: {s}")

    def build_pipeline(self, pipe: Pipeline) -> IRNode:
        expr = self.build_node(pipe.source)
        for stage in pipe.stages:
            py_name = BUILTIN_PYTHON.get(stage.name, stage.name)
            args = [self.build_arg(a) for a in stage.args]
            args.append(expr)
            expr = IRCall(func=py_name, args=args)
        return expr

    def build_arg(self, arg) -> IRNode:
        # Args vindas do parser são sempre Pipeline (podem ter 0 estágios).
        if isinstance(arg, Pipeline) and not arg.stages:
            arg = arg.source

        if has_implicit(arg):
            return IRLambda(
                param=LAMBDA_PARAM,
                body=self.build_node(arg, implicit=LAMBDA_PARAM),
            )
        return self.build_node(arg, implicit=None)

    def build_node(self, node, implicit=None) -> IRNode:
        if isinstance(node, ImplicitField):
            if implicit is None:
                raise Exception("'.' fora de contexto de estágio")
            return IRField(obj=IRVar(name=implicit), field=node.field)

        if isinstance(node, FieldAccess):
            return IRField(obj=self.build_node(node.obj, implicit),
                           field=node.field)

        if isinstance(node, Identifier):
            return IRVar(name=node.name)
        if isinstance(node, NumberLit):
            return IRNum(value=node.value)
        if isinstance(node, StringLit):
            return IRStr(value=node.value)
        if isinstance(node, BoolLit):
            return IRBool(value=node.value)

        if isinstance(node, ListLit):
            return IRList(items=[self.build_pipeline(i) for i in node.items])
        if isinstance(node, DictLit):
            return IRDict(pairs=[(k, self.build_pipeline(v)) for k, v in node.pairs])

        if isinstance(node, Pipeline):
            return self.build_pipeline(node)

        if isinstance(node, BinaryOp):
            return IRBinOp(op=node.op,
                           left=self.build_node(node.left, implicit),
                           right=self.build_node(node.right, implicit))
        if isinstance(node, UnaryOp):
            return IRUnOp(op=node.op,
                          operand=self.build_node(node.operand, implicit))

        if isinstance(node, Call):
            py_name = BUILTIN_PYTHON.get(node.name, node.name)
            args = [self.build_arg(a) for a in node.args]
            return IRCall(func=py_name, args=args)

        raise Exception(f"unknown node: {node}")