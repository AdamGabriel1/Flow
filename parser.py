from tokens import Token, TokenType
from ast_nodes import *
from lexer import FlowError


class ParseError(FlowError):
    def kind(self):
        return "Parse"


# Mapa de precedência para operadores binários de comparação
CMP_OPS = {
    TokenType.EQEQ: "==",
    TokenType.NEQ:  "!=",
    TokenType.LT:   "<",
    TokenType.GT:   ">",
    TokenType.LE:   "<=",
    TokenType.GE:   ">=",
}


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset=0):
        i = self.pos + offset
        if i >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[i]

    def advance(self):
        tok = self.tokens[self.pos]
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def check(self, ttype):
        return self.peek().type == ttype

    def match(self, *ttypes):
        if self.peek().type in ttypes:
            return self.advance()
        return None

    def expect(self, ttype, msg=None):
        if self.peek().type == ttype:
            return self.advance()
        raise ParseError(
            msg or f"expected {ttype.name}, got {self.peek().type.name}",
            self.peek().line, self.peek().col,
        )

    def skip_newlines(self):
        while self.check(TokenType.NEWLINE):
            self.advance()

    # ─── program ────────────────────────────────────────────

    def parse_program(self):
        prog = Program()
        self.skip_newlines()
        while not self.check(TokenType.EOF):
            prog.statements.append(self.parse_statement())
            self.skip_newlines()
        return prog

    def parse_statement(self):
        if self.check(TokenType.FN):
            return self.parse_fndef()

        if (self.peek().type == TokenType.IDENT
                and self.peek(1).type == TokenType.EQUALS):
            name_tok = self.advance()
            self.expect(TokenType.EQUALS, "expected '='")
            value = self.parse_pipeline()
            return Assignment(name=name_tok.value, value=value, line=name_tok.line)

        return ExprStatement(expr=self.parse_pipeline(), line=self.peek().line)

    def parse_fndef(self):
        kw = self.advance()
        name_tok = self.expect(TokenType.IDENT, "expected function name after 'fn'")
        self.expect(TokenType.LPAREN, "expected '(' after function name")
        self.skip_newlines()
        params = []
        if not self.check(TokenType.RPAREN):
            params.append(self.expect(TokenType.IDENT, "expected parameter name").value)
            self.skip_newlines()
            while self.match(TokenType.COMMA):
                self.skip_newlines()
                params.append(self.expect(TokenType.IDENT, "expected parameter name").value)
                self.skip_newlines()
        self.expect(TokenType.RPAREN, "expected ')'")
        self.expect(TokenType.COLON, "expected ':' after function signature")
        self.skip_newlines()
        body = self.parse_pipeline()
        return FnDef(name=name_tok.value, params=params, body=body, line=kw.line)

    # ─── pipeline ───────────────────────────────────────────

    def parse_pipeline(self):
        source = self.parse_expr()
        stages = []
        save = self.pos
        self.skip_newlines()
        while self.check(TokenType.PIPE):
            self.advance()
            self.skip_newlines()
            stages.append(self.parse_stage())
            save = self.pos
            self.skip_newlines()
        if not stages:
            self.pos = save
        return Pipeline(source=source, stages=stages)

    def parse_stage(self):
        name_tok = self.expect(TokenType.IDENT, "expected stage name")
        self.expect(TokenType.LPAREN, "expected '(' after stage name")
        args = []
        self.skip_newlines()
        if not self.check(TokenType.RPAREN):
            args.append(self.parse_pipeline())
            self.skip_newlines()
            while self.match(TokenType.COMMA):
                self.skip_newlines()
                if self.check(TokenType.RPAREN):
                    break  # trailing comma
                args.append(self.parse_pipeline())
                self.skip_newlines()
        self.expect(TokenType.RPAREN, "expected ')'")
        return StageCall(name=name_tok.value, args=args, line=name_tok.line)

    # ─── expressões (precedência crescente) ────────────────

    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.match(TokenType.OR):
            left = BinaryOp(op="or", left=left,
                            right=self.parse_and(), line=left.line)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.match(TokenType.AND):
            left = BinaryOp(op="and", left=left,
                            right=self.parse_not(), line=left.line)
        return left

    def parse_not(self):
        if self.match(TokenType.NOT):
            return UnaryOp(op="not", operand=self.parse_not(),
                           line=self.tokens[self.pos - 1].line)
        return self.parse_cmp()

    def parse_cmp(self):
        left = self.parse_add()
        if self.peek().type in CMP_OPS:
            op_tok = self.advance()
            return BinaryOp(op=CMP_OPS[op_tok.type], left=left,
                            right=self.parse_add(), line=op_tok.line)
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.peek().type in (TokenType.PLUS, TokenType.MINUS):
            op_tok = self.advance()
            left = BinaryOp(op=op_tok.value, left=left,
                            right=self.parse_mul(), line=op_tok.line)
        return left

    def parse_mul(self):
        left = self.parse_unary()
        while self.peek().type in (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op_tok = self.advance()
            left = BinaryOp(op=op_tok.value, left=left,
                            right=self.parse_unary(), line=op_tok.line)
        return left

    def parse_unary(self):
        if self.match(TokenType.MINUS):
            return UnaryOp(op="-", operand=self.parse_unary(),
                           line=self.tokens[self.pos - 1].line)
        return self.parse_postfix()

    def parse_postfix(self):
        expr = self.parse_primary()
        while self.check(TokenType.DOT):
            self.advance()
            field_tok = self.expect(TokenType.IDENT, "expected field name after '.'")
            expr = FieldAccess(obj=expr, field=field_tok.value, line=field_tok.line)
        return expr

    # ─── primary ────────────────────────────────────────────

    def parse_primary(self):
        tok = self.peek()

        if tok.type == TokenType.DOT:
            self.advance()
            field_tok = self.expect(TokenType.IDENT, "expected field name after '.'")
            return ImplicitField(field=field_tok.value, line=field_tok.line)

        if tok.type == TokenType.IDENT:
            if self.peek(1).type == TokenType.LPAREN:
                return self.parse_call()
            self.advance()
            return Identifier(name=tok.value, line=tok.line)

        if tok.type == TokenType.NUMBER:
            self.advance()
            val = float(tok.value) if '.' in tok.value else int(tok.value)
            return NumberLit(value=val, line=tok.line)

        if tok.type == TokenType.STRING:
            self.advance()
            return StringLit(value=tok.value, line=tok.line)

        if tok.type == TokenType.TRUE:
            self.advance()
            return BoolLit(value=True, line=tok.line)

        if tok.type == TokenType.FALSE:
            self.advance()
            return BoolLit(value=False, line=tok.line)

        if tok.type == TokenType.LBRACKET:
            return self.parse_list()

        if tok.type == TokenType.LBRACE:
            return self.parse_dict()

        if tok.type == TokenType.LPAREN:
            self.advance()
            inner = self.parse_pipeline()
            self.expect(TokenType.RPAREN, "expected ')'")
            return inner

        raise ParseError(f"unexpected token {tok.type.name}", tok.line, tok.col)

    # ─── chamada em posição de expressão ───────────────────

    def parse_call(self):
        name_tok = self.expect(TokenType.IDENT)
        self.expect(TokenType.LPAREN)
        args = []
        self.skip_newlines()
        if not self.check(TokenType.RPAREN):
            args.append(self.parse_pipeline())
            self.skip_newlines()
            while self.match(TokenType.COMMA):
                self.skip_newlines()
                if self.check(TokenType.RPAREN):
                    break
                args.append(self.parse_pipeline())
                self.skip_newlines()
        self.expect(TokenType.RPAREN)
        return Call(name=name_tok.value, args=args, line=name_tok.line)

    # ─── listas e dicionários ──────────────────────────────

    def parse_list(self):
        self.expect(TokenType.LBRACKET)
        self.skip_newlines()
        items = []
        if not self.check(TokenType.RBRACKET):
            items.append(self.parse_pipeline())
            self.skip_newlines()
            while self.match(TokenType.COMMA):
                self.skip_newlines()
                if self.check(TokenType.RBRACKET):
                    break
                items.append(self.parse_pipeline())
                self.skip_newlines()
        self.expect(TokenType.RBRACKET)
        return ListLit(items=items)

    def parse_dict(self):
        self.expect(TokenType.LBRACE)
        self.skip_newlines()
        pairs = []
        if not self.check(TokenType.RBRACE):
            pairs.append(self.parse_dict_pair())
            self.skip_newlines()
            while self.match(TokenType.COMMA):
                self.skip_newlines()
                if self.check(TokenType.RBRACE):
                    break
                pairs.append(self.parse_dict_pair())
                self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return DictLit(pairs=pairs)

    def parse_dict_pair(self):
        key_tok = self.peek()
        if key_tok.type in (TokenType.STRING, TokenType.IDENT):
            self.advance()
            key = key_tok.value
        else:
            raise ParseError("expected string or identifier as dict key",
                             key_tok.line, key_tok.col)
        self.expect(TokenType.COLON, "expected ':' after dict key")
        self.skip_newlines()
        value = self.parse_pipeline()
        return (key, value)