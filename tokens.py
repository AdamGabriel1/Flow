from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    IDENT = auto()
    NUMBER = auto()
    STRING = auto()
    TRUE = auto()
    FALSE = auto()
    FN = auto()
    LBRACKET = auto(); RBRACKET = auto()
    LBRACE = auto();   RBRACE = auto()
    LPAREN = auto();   RPAREN = auto()
    COMMA = auto();    COLON = auto()
    PIPE = auto()      # |>
    EQUALS = auto()    # =
    DOT = auto()       # .
    PLUS = auto(); MINUS = auto()
    STAR = auto(); SLASH = auto(); PERCENT = auto()
    EQEQ = auto(); NEQ = auto()
    LT = auto();   GT = auto();  LE = auto();  GE = auto()
    AND = auto();  OR = auto();  NOT = auto()
    NEWLINE = auto(); EOF = auto()


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.col})"