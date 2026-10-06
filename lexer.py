from tokens import Token, TokenType


KEYWORDS = {
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "fn": TokenType.FN,
}


class FlowError(Exception):
    """Base class for all Flow compiler errors."""
    def __init__(self, msg, line=None, col=None):
        loc = f" at {line}:{col}" if line is not None else ""
        super().__init__(f"{self.kind()} error{loc}: {msg}")
        self.line = line
        self.col = col

    def kind(self):
        return "Flow"


class LexerError(FlowError):
    def kind(self):
        return "Lexer"


MULTI_CHARS = {
    '|>': TokenType.PIPE,
    '==': TokenType.EQEQ,
    '!=': TokenType.NEQ,
    '<=': TokenType.LE,
    '>=': TokenType.GE,
}

SINGLE_CHARS = {
    '[': TokenType.LBRACKET,
    ']': TokenType.RBRACKET,
    '{': TokenType.LBRACE,
    '}': TokenType.RBRACE,
    '(': TokenType.LPAREN,
    ')': TokenType.RPAREN,
    ',': TokenType.COMMA,
    ':': TokenType.COLON,
    '=': TokenType.EQUALS,
    '.': TokenType.DOT,
    '+': TokenType.PLUS,
    '-': TokenType.MINUS,
    '*': TokenType.STAR,
    '/': TokenType.SLASH,
    '%': TokenType.PERCENT,
    '<': TokenType.LT,
    '>': TokenType.GT,
}


class Lexer:
    def __init__(self, src):
        self.src = src
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []

    def peek(self, offset=0):
        i = self.pos + offset
        return self.src[i] if i < len(self.src) else '\0'

    def advance(self):
        ch = self.src[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    @staticmethod
    def is_ident_start(ch):
        return ch.isalpha() or ch == '_'

    @staticmethod
    def is_ident_part(ch):
        return ch.isalnum() or ch == '_'

    def lex(self):
        while self.pos < len(self.src):
            ch = self.peek()

            if ch in ' \t\r':
                self.advance()
                continue

            if ch == '\n':
                self.tokens.append(Token(TokenType.NEWLINE, '\n', self.line, self.col))
                self.advance()
                continue

            if ch == '#':
                while self.peek() not in ('\n', '\0'):
                    self.advance()
                continue

            if self.is_ident_start(ch):
                start = self.pos
                sl, sc = self.line, self.col
                while self.is_ident_part(self.peek()):
                    self.advance()
                word = self.src[start:self.pos]
                self.tokens.append(Token(
                    KEYWORDS.get(word, TokenType.IDENT),
                    word, sl, sc
                ))
                continue

            if ch.isdigit() or (ch == '.' and self.peek(1).isdigit()):
                start = self.pos
                sl, sc = self.line, self.col
                seen_dot = False
                while self.peek().isdigit() or (self.peek() == '.' and not seen_dot):
                    if self.peek() == '.':
                        seen_dot = True
                    self.advance()
                num = self.src[start:self.pos]
                self.tokens.append(Token(TokenType.NUMBER, num, sl, sc))
                continue

            if ch == '"' or ch == "'":
                quote = ch
                sl, sc = self.line, self.col
                self.advance()
                buf = []
                while self.peek() != quote and self.peek() != '\0':
                    if self.peek() == '\\':
                        self.advance()
                        esc = self.advance()
                        mapping = {'n': '\n', 't': '\t', 'r': '\r',
                                   '\\': '\\', '"': '"', "'": "'"}
                        buf.append(mapping.get(esc, esc))
                    else:
                        buf.append(self.advance())
                if self.peek() == '\0':
                    raise LexerError("unterminated string", sl, sc)
                self.advance()
                self.tokens.append(Token(TokenType.STRING, ''.join(buf), sl, sc))
                continue

            # operadores de dois caracteres primeiro
            two = self.src[self.pos:self.pos + 2]
            if two in MULTI_CHARS:
                tok = Token(MULTI_CHARS[two], two, self.line, self.col)
                self.advance(); self.advance()
                self.tokens.append(tok)
                continue

            if ch in SINGLE_CHARS:
                tok = Token(SINGLE_CHARS[ch], ch, self.line, self.col)
                self.advance()
                self.tokens.append(tok)
                continue

            raise LexerError(f"unexpected character {ch!r}", self.line, self.col)

        self.tokens.append(Token(TokenType.EOF, '', self.line, self.col))
        return self.tokens