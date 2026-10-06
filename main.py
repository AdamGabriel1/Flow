"""Flow — uma linguagem de pipelines que transpila para Python.

Uso:
    python main.py examples/users.flow            # imprime Python gerado
    python main.py users.flow -o users.py         # escreve arquivo
    python main.py users.flow --ast               # imprime AST
    python main.py users.flow --ir                # imprime IR
    python main.py users.flow --no-typecheck      # pula type checking
    python main.py users.flow --run               # executa o Python gerado
"""
import sys

from lexer import Lexer, FlowError
from parser import Parser
from name_resolver import NameResolver
from type_checker import TypeChecker
from ir_builder import IRBuilder
from python_gen import PythonGenerator
from flow_types import TypeError_


def _dump_ast(node, depth=0):
    indent = "  " * depth
    if isinstance(node, list):
        for x in node:
            _dump_ast(x, depth)
        return
    if hasattr(node, "__dataclass_fields__"):
        print(f"{indent}{type(node).__name__}")
        for f in node.__dataclass_fields__:
            val = getattr(node, f)
            if hasattr(val, "__dataclass_fields__") or isinstance(val, list):
                print(f"{indent}  {f}:")
                _dump_ast(val, depth + 2)
            else:
                print(f"{indent}  {f}: {val!r}")
    else:
        print(f"{indent}{node!r}")


def compile_source(src: str, do_typecheck: bool = True):
    """source → tokens → AST → name-resolve → type-check → IR → Python."""
    tokens = Lexer(src).lex()
    ast_root = Parser(tokens).parse_program()
    NameResolver().resolve_program(ast_root)
    if do_typecheck:
        TypeChecker().check_program(ast_root)
    ir = IRBuilder().build_program(ast_root)
    py = PythonGenerator().generate(ir)
    return ast_root, ir, py


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    path = argv[0]
    flags = argv[1:]

    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        print(f"cannot read {path}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        ast_root, ir, py = compile_source(
            src, do_typecheck=("--no-typecheck" not in flags)
        )
    except (FlowError, TypeError_) as e:
        print(f"{path}: {e}", file=sys.stderr)
        sys.exit(1)

    if "--ast" in flags:
        print("=== AST ===")
        _dump_ast(ast_root)
        print()

    if "--ir" in flags:
        print("=== IR ===")
        print(ir)
        print()

    if "--run" in flags:
        exec(py, {"__name__": "__main__"})
        return

    if "-o" in flags:
        idx = flags.index("-o")
        if idx + 1 >= len(flags):
            print("-o requires a path", file=sys.stderr)
            sys.exit(1)
        out_path = flags[idx + 1]
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(py)
        print(f"wrote {out_path} ({len(py)} bytes)", file=sys.stderr)
    else:
        print(py)


if __name__ == "__main__":
    main()