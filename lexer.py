"""
lexer.py — RecipeLang Phase 1 Lexical Analyzer

Converts RecipeLang source text into a stream of tokens.
This is the FIRST stage of the compiler pipeline:

    Source Code --> [LEXER] --> Tokens --> Parser ...

Only lexical analysis rules live here. No grammar/syntax checking,
and no semantic checking (those belong to the Parser and later phases).
"""

import re

# ---------------------------------------------------------------------------
# Token specification (order matters — first match wins)
# ---------------------------------------------------------------------------
KEYWORDS = {"RECIPE", "INGREDIENT", "STEP", "SERVES", "REPEAT", "DIET", "AVOID", "DEFINE", "END", "CALL"}

UNITS = {"cups", "cup", "tbsp", "tsp", "g", "kg", "ml", "l", "pieces", "piece"}
TIMEUNITS = {"minutes", "minute", "seconds", "second", "hours", "hour"}

TOKEN_SPEC = [
    ("NUMBER",      r"\d+"),
    ("ASSIGN",      r"="),
    ("LPAREN",      r"\("),
    ("RPAREN",      r"\)"),
    ("COMMA",       r","),
    ("NEWLINE",     r"\n"),
    ("SKIP",        r"[ \t]+"),
    ("IDENT",       r"[A-Za-z_][A-Za-z0-9_]*"),
    ("MISMATCH",    r"."),   # anything else = lexical error
]

MASTER_PATTERN = "|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC)
TOKEN_REGEX = re.compile(MASTER_PATTERN)


class Token:
    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line}, col={self.col})"


class LexicalError(Exception):
    pass


def tokenize(source: str):
    """
    Converts RecipeLang source text into a list of Token objects.
    Raises LexicalError on any character that cannot be classified.
    """
    tokens = []
    line_num = 1
    line_start = 0

    for match in TOKEN_REGEX.finditer(source):
        kind = match.lastgroup
        value = match.group()
        col = match.start() - line_start + 1

        if kind == "NEWLINE":
            line_num += 1
            line_start = match.end()
            continue
        elif kind == "SKIP":
            continue
        elif kind == "MISMATCH":
            raise LexicalError(
                f"Lexical Error: unexpected character {value!r} "
                f"at line {line_num}, column {col}"
            )
        elif kind == "IDENT":
            if value in KEYWORDS:
                kind = "KEYWORD"
            elif value in UNITS:
                kind = "UNIT"
            elif value in TIMEUNITS:
                kind = "TIMEUNIT"
            else:
                kind = "IDENT"

        tokens.append(Token(kind, value, line_num, col))

    tokens.append(Token("EOF", "", line_num, 0))
    return tokens


if __name__ == "__main__":
    sample = open("sample_input.recipe").read()
    for tok in tokenize(sample):
        print(tok)
