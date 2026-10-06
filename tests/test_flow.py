"""Testes do compilador Flow. Rode com `python tests/test_flow.py`."""
import io
import os
import sys
import contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from main import compile_source
from lexer import Lexer, FlowError
from tokens import TokenType
from parser import Parser
from ast_nodes import Program, Assignment, FnDef, BinaryOp, ImplicitField
from flow_types import TypeError_


def compile_and_run(src):
    ast, ir, py = compile_source(src)
    buf = io.StringIO()
    ns = {}
    with contextlib.redirect_stdout(buf):
        exec(py, ns)
    return py, buf.getvalue()


# ─── lexer ──────────────────────────────────────────────────

def test_lexer_predicate():
    toks = Lexer(".age > 18 and .active").lex()
    types = [t.type for t in toks]
    assert TokenType.DOT in types
    assert TokenType.GT in types
    assert TokenType.NUMBER in types
    assert TokenType.AND in types


def test_lexer_operators():
    toks = Lexer("a == b != c <= d >= e").lex()
    assert [t.type for t in toks[:-1]] == [
        TokenType.IDENT, TokenType.EQEQ, TokenType.IDENT,
        TokenType.NEQ, TokenType.IDENT, TokenType.LE,
        TokenType.IDENT, TokenType.GE, TokenType.IDENT,
    ]


# ─── parser ─────────────────────────────────────────────────

def test_parse_assignment():
    prog = Parser(Lexer("x = 1").lex()).parse_program()
    assert isinstance(prog, Program)
    assert isinstance(prog.statements[0], Assignment)


def test_parse_fndef():
    prog = Parser(Lexer("fn double(x):\n    x * 2").lex()).parse_program()
    assert isinstance(prog.statements[0], FnDef)


def test_parse_predicate():
    prog = Parser(Lexer("d |> filter(.a > 1 and .b)").lex()).parse_program()
    stage = prog.statements[0].expr.stages[0]
    arg = stage.args[0].source
    assert isinstance(arg, BinaryOp) and arg.op == "and"


# ─── pipeline + predicados ─────────────────────────────────
#
# Nota: `map` e `filter` do Python 3 são preguiçosos — devolvem iteradores.
# Para observar a sequência, materializamos com `list()` como último estágio
# antes do `print()`. É a mesma disciplina que se usa em Python "puro".

def test_simple_predicate():
    src = """
data = [{age: 10, name: "a"}, {age: 20, name: "b"}, {age: 30, name: "c"}]
data |> filter(.age > 15) |> map(.name) |> list() |> print()
"""
    py, out = compile_and_run(src)
    assert "_x['age'] > 15" in py          # ← era "_x.age > 15"
    assert "['b', 'c']" in out


def test_boolean_predicate():
    src = """
data = [
    {age: 20, active: true},
    {age: 15, active: true},
    {age: 25, active: false},
]
data |> filter(.age > 18 and .active) |> map(.age) |> list() |> print()
"""
    _, out = compile_and_run(src)
    assert "[20]" in out


def test_nested_field():
    src = """
data = [{c: {v: 1}}, {c: {v: 2}}]
data |> map(.c.v) |> list() |> print()
"""
    _, out = compile_and_run(src)
    assert "[1, 2]" in out


def test_lazy_iterator_semantics():
    """Documenta o comportamento: sem materializar, o estágio final é um
    iterador e `print` mostra o repr do objeto — não uma lista."""
    src = """
nums = [{x: 1}, {x: 2}, {x: 3}]
nums |> map(.x) |> print()
"""
    _, out = compile_and_run(src)
    assert "map object" in out


def test_field_access_emits_subscript():
    src = """
data = [{name: "a"}]
data |> map(.name) |> list() |> print()
"""
    py, out = compile_and_run(src)
    assert "_x['name']" in py           # não `_x.name`
    assert "['a']" in out


# ─── funções de usuário ────────────────────────────────────

def test_user_fn_as_stage_arg():
    src = """
fn double(n):
    n * 2

nums = [1, 2, 3]
nums |> map(double) |> list() |> print()
"""
    py, out = compile_and_run(src)
    assert "def double(n):" in py
    assert "[2, 4, 6]" in out


def test_user_fn_in_predicate_position():
    src = """
fn big(n):
    n > 5

nums = [3, 7, 9]
nums |> filter(big) |> list() |> print()
"""
    _, out = compile_and_run(src)
    assert "[7, 9]" in out


# ─── erros ──────────────────────────────────────────────────

def test_type_error_filter_on_nonlist():
    src = "x = 5\nx |> filter(.a) |> print()"
    try:
        compile_source(src)
    except (FlowError, TypeError_):
        return
    raise AssertionError("esperava erro de tipo")


def test_name_error():
    try:
        compile_source("nope |> print()")
    except FlowError as e:
        assert "undefined" in str(e).lower()
        return
    raise AssertionError("esperava NameError")


# ─── runner ────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok  {name}")
        except Exception as e:
            print(f" FAIL {name}: {e!r}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passaram")
    sys.exit(1 if failed else 0)