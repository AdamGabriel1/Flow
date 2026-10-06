"""Type-checks a Flow AST.

Cada builtin é descrita por uma *type scheme factory*: uma função sem
argumentos que devolve um `TFunc` fresco, dando polimorfismo paramétrico a
`filter`, `map`, etc. `fn` de usuário recebe uma assinatura fresca no
pré-pass e é monomórfica no seu uso.
"""
from ast_nodes import *
from flow_types import (
    Type, TInt, TFloat, TStr, TBool, TNone,
    TList, TSet, TDict, TRecord, TFunc, TVar,
    fresh, resolve, unify, TypeError_,
)


# ─── schemes dos builtins ──────────────────────────────────

def _filter_scheme():
    t = fresh()
    return TFunc([TFunc([t], TBool()), TList(t)], TList(t))


def _map_scheme():
    a, b = fresh(), fresh()
    return TFunc([TFunc([a], b), TList(a)], TList(b))


def _unique_scheme():
    """Dedupe. Ao nível de *tipos* devolvemos List, embora o Python emitido
    seja `set(...)`. Sem isso, `unique |> sort` não typechecka — e a stdlib
    do Python aceita `sorted(set)` sem drama. É uma simplificação deliberada:
    o sistema de tipos não tem union/iterable ainda."""
    t = fresh()
    return TFunc([TList(t)], TList(t))


def _sort_scheme():
    t = fresh()
    return TFunc([TList(t)], TList(t))


def _print_scheme():
    t = fresh()
    return TFunc([t], TNone())


def _len_scheme():
    t = fresh()
    return TFunc([TList(t)], TInt())


def _range_scheme():
    return TFunc([TInt()], TList(TInt()))


def _sum_scheme():
    return TFunc([TList(TInt())], TInt())


def _opaque(nargs=1):
    """Função genérica `(a, b, ...) -> c` — usada para builtins menos
    interessantes (`str`, `int`, `list`, ...)."""
    def factory():
        params = [fresh() for _ in range(nargs)]
        return TFunc(params, fresh())
    return factory


BUILTIN_SCHEMES = {
    "filter": _filter_scheme,
    "map": _map_scheme,
    "unique": _unique_scheme,
    "sort": _sort_scheme,
    "print": _print_scheme,
    "len": _len_scheme,
    "range": _range_scheme,
    "sum": _sum_scheme,
    "str":   lambda: _opaque(1)(),
    "int":   lambda: _opaque(1)(),
    "float": lambda: _opaque(1)(),
    "bool":  lambda: _opaque(1)(),
    "list":  lambda: _opaque(1)(),
    "set":   lambda: _opaque(1)(),
    "dict":  lambda: _opaque(1)(),
    "min":   lambda: TFunc([TList(fresh())], fresh()),
    "max":   lambda: TFunc([TList(fresh())], fresh()),
    "reversed": lambda: TFunc([TList(fresh())], TList(fresh())),
    "abs":   lambda: TFunc([TInt()], TInt()),
    "round": lambda: TFunc([TFloat()], TInt()),
    "any":   lambda: TFunc([TList(TBool())], TBool()),
    "all":   lambda: TFunc([TList(TBool())], TBool()),
}


class TypeChecker:
    def __init__(self):
        self.env: dict[str, Type] = {}

    def lookup(self, name: str) -> Type | None:
        if name in self.env:
            return self.env[name]
        if name in BUILTIN_SCHEMES:
            return BUILTIN_SCHEMES[name]()
        return None

    def check_program(self, prog: Program):
        # Pré-pass: assinaturas de `fn` para permitir forward references.
        for stmt in prog.statements:
            if isinstance(stmt, FnDef):
                self.env[stmt.name] = self._fn_signature(stmt)
        for stmt in prog.statements:
            self.check_stmt(stmt)

    def _fn_signature(self, fndef: FnDef) -> TFunc:
        params = [fresh() for _ in fndef.params]
        saved = dict(self.env)
        for name, t in zip(fndef.params, params):
            self.env[name] = t
        ret = self.infer_pipeline(fndef.body)
        self.env = saved
        return TFunc(params, resolve(ret))

    def check_stmt(self, stmt):
        if isinstance(stmt, FnDef):
            return  # já tratada no pré-pass
        if isinstance(stmt, Assignment):
            self.env[stmt.name] = self.infer_pipeline(stmt.value)
        elif isinstance(stmt, ExprStatement):
            self.infer_pipeline(stmt.expr)

    # ─── inferência ────────────────────────────────────────

    def infer_pipeline(self, pipe: Pipeline) -> Type:
        t = self.infer_node(pipe.source, implicit=None)
        for stage in pipe.stages:
            t = self.infer_stage(stage, t)
        return resolve(t)

    def infer_stage(self, stage: StageCall, input_t: Type) -> Type:
        fn_t = self.lookup(stage.name)
        if fn_t is None:
            raise TypeError_(f"undefined function '{stage.name}'", stage)
        arg_types = [self.infer_arg(a) for a in stage.args]
        arg_types.append(input_t)
        ret = fresh()
        unify(fn_t, TFunc(arg_types, ret))
        return resolve(ret)

    def infer_arg(self, arg) -> Type:
        """Argumento com `.field` vira `lambda _x: ...`. O tipo é
        `TFunc([elem], body)` onde `elem` é um registro aberto que acumula
        os campos exigidos por `.` dentro de `arg`."""
        if has_implicit(arg):
            elem = TRecord({}, open=True)
            body_t = self.infer_node(arg, implicit=elem)
            return TFunc([elem], body_t)
        return self.infer_node(arg, implicit=None)

    def infer_node(self, node, implicit: TRecord | None) -> Type:
        if isinstance(node, ImplicitField):
            if implicit is None:
                raise TypeError_(
                    "'.' só pode ser usado como argumento de um estágio", node)
            if node.field not in implicit.fields:
                implicit.fields[node.field] = fresh()
            return implicit.fields[node.field]

        if isinstance(node, FieldAccess):
            obj_t = self.infer_node(node.obj, implicit)
            field_t = fresh()
            unify(obj_t, TRecord({node.field: field_t}, open=True))
            return resolve(field_t)

        if isinstance(node, Identifier):
            t = self.lookup(node.name)
            if t is None:
                raise TypeError_(f"undefined name '{node.name}'", node)
            return t

        if isinstance(node, NumberLit):
            return TInt() if isinstance(node.value, int) else TFloat()
        if isinstance(node, StringLit):
            return TStr()
        if isinstance(node, BoolLit):
            return TBool()

        if isinstance(node, ListLit):
            if not node.items:
                return TList(fresh())
            elem = self.infer_node(node.items[0], implicit)
            for it in node.items[1:]:
                unify(elem, self.infer_node(it, implicit))
            return TList(elem)

        if isinstance(node, DictLit):
            return TRecord({k: self.infer_node(v, implicit)
                            for k, v in node.pairs})

        if isinstance(node, Pipeline):
            t = self.infer_node(node.source, implicit)
            for stage in node.stages:
                t = self.infer_stage(stage, t)
            return resolve(t)

        if isinstance(node, BinaryOp):
            lt = self.infer_node(node.left, implicit)
            rt = self.infer_node(node.right, implicit)
            if node.op in ("==", "!=", "<", ">", "<=", ">="):
                unify(lt, rt)
                return TBool()
            if node.op in ("and", "or"):
                unify(lt, TBool())
                unify(rt, TBool())
                return TBool()
            if node.op in ("+", "-", "*", "/", "%"):
                unify(lt, rt)
                return resolve(lt)
            raise TypeError_(f"operador desconhecido '{node.op}'", node)

        if isinstance(node, UnaryOp):
            t = self.infer_node(node.operand, implicit)
            if node.op == "not":
                unify(t, TBool())
                return TBool()
            if node.op == "-":
                unify(t, TInt())
                return TInt()
            raise TypeError_(f"operador unário desconhecido '{node.op}'", node)

        if isinstance(node, Call):
            fn_t = self.lookup(node.name)
            if fn_t is None:
                raise TypeError_(f"undefined function '{node.name}'", node)
            arg_types = [self.infer_node(a, implicit) for a in node.args]
            ret = fresh()
            unify(fn_t, TFunc(arg_types, ret))
            return resolve(ret)

        raise TypeError_(f"não sei inferir tipo para {type(node).__name__}", node)


def has_implicit(node) -> bool:
    """True se `node` referencia `.field` em qualquer profundidade —
    sinal de que o argumento deve virar uma lambda."""
    if isinstance(node, ImplicitField):
        return True
    if isinstance(node, FieldAccess):
        return has_implicit(node.obj)
    if isinstance(node, BinaryOp):
        return has_implicit(node.left) or has_implicit(node.right)
    if isinstance(node, UnaryOp):
        return has_implicit(node.operand)
    if isinstance(node, Call):
        return any(has_implicit(a) for a in node.args)
    if isinstance(node, Pipeline):
        if has_implicit(node.source):
            return True
        return any(has_implicit(a) for s in node.stages for a in s.args)
    if isinstance(node, ListLit):
        return any(has_implicit(i) for i in node.items)
    if isinstance(node, DictLit):
        return any(has_implicit(v) for _, v in node.pairs)
    return False