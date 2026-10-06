"""Sistema de tipos com variáveis de tipo e unificação estrutural.

Registros são *abertos*: `TRecord({...}, open=True)` aceita campos extras
na unificação — usado para o argumento implícito `.field`.
"""
from typing import List, Dict, Optional


class Type:
    pass


class TInt(Type):
    def __repr__(self): return "Int"
    def __eq__(self, o): return isinstance(o, TInt)
    def __hash__(self): return hash("Int")


class TFloat(Type):
    def __repr__(self): return "Float"
    def __eq__(self, o): return isinstance(o, TFloat)
    def __hash__(self): return hash("Float")


class TStr(Type):
    def __repr__(self): return "Str"
    def __eq__(self, o): return isinstance(o, TStr)
    def __hash__(self): return hash("Str")


class TBool(Type):
    def __repr__(self): return "Bool"
    def __eq__(self, o): return isinstance(o, TBool)
    def __hash__(self): return hash("Bool")


class TNone(Type):
    def __repr__(self): return "None"
    def __eq__(self, o): return isinstance(o, TNone)
    def __hash__(self): return hash("None")


class TList(Type):
    def __init__(self, elem): self.elem = elem
    def __repr__(self): return f"List[{self.elem}]"


class TSet(Type):
    def __init__(self, elem): self.elem = elem
    def __repr__(self): return f"Set[{self.elem}]"


class TDict(Type):
    def __init__(self, k, v): self.k, self.v = k, v
    def __repr__(self): return f"Dict[{self.k}, {self.v}]"


class TRecord(Type):
    def __init__(self, fields: Dict[str, Type], open: bool = False):
        self.fields = dict(fields)
        self.open = open
    def __repr__(self):
        inner = ", ".join(f"{k}: {v}" for k, v in self.fields.items())
        return "{" + inner + ("; ..." if self.open else "") + "}"


class TFunc(Type):
    def __init__(self, params: List[Type], ret: Type):
        self.params, self.ret = params, ret
    def __repr__(self):
        return f"({', '.join(repr(p) for p in self.params)}) -> {self.ret}"


class TVar(Type):
    _counter = 0
    def __init__(self):
        TVar._counter += 1
        self.id = TVar._counter
        self._instance: Optional[Type] = None

    def prune(self):
        if self._instance is None:
            return self
        if isinstance(self._instance, TVar):
            root = self._instance.prune()
            self._instance = root
            return root
        return self._instance

    def set(self, t):
        # guarda: nunca ligar uma variável a si mesma
        if t is self:
            return
        self._instance = t

    def __repr__(self):
        r = self.prune()
        return f"t{self.id}" if r is self else repr(r)


def fresh() -> TVar:
    return TVar()


def resolve(t: Type) -> Type:
    while isinstance(t, TVar):
        r = t.prune()
        if r is t:
            return t
        t = r
    return t


class TypeError_(Exception):
    def __init__(self, msg, node=None):
        line = getattr(node, "line", "?") if node is not None else "?"
        super().__init__(f"Type error at line {line}: {msg}")


def unify(a: Type, b: Type):
    a = resolve(a)
    b = resolve(b)

    # Guarda: `unify(t, t)` é no-op
    if a is b:
        return

    if isinstance(a, TVar):
        a.set(b); return
    if isinstance(b, TVar):
        b.set(a); return

    if isinstance(a, TList) and isinstance(b, TList):
        unify(a.elem, b.elem); return
    if isinstance(a, TSet) and isinstance(b, TSet):
        unify(a.elem, b.elem); return
    if isinstance(a, TDict) and isinstance(b, TDict):
        unify(a.k, b.k); unify(a.v, b.v); return

    if isinstance(a, TRecord) and isinstance(b, TRecord):
        for k, tv in a.fields.items():
            if k in b.fields:
                unify(tv, b.fields[k])
            elif not b.open:
                raise TypeError_(f"record missing field '{k}'")
        for k, tv in b.fields.items():
            if k in a.fields:
                continue
            if not a.open:
                raise TypeError_(f"record missing field '{k}'")
        return

    if isinstance(a, TFunc) and isinstance(b, TFunc):
        if len(a.params) != len(b.params):
            raise TypeError_(f"function arity mismatch: {a} vs {b}")
        for pa, pb in zip(a.params, b.params):
            unify(pa, pb)
        unify(a.ret, b.ret); return

    if type(a) is type(b):
        return

    raise TypeError_(f"cannot unify {a} with {b}")