"""
parser.py — RecipeLang Phase 1 Parser (structural / syntax validation)

This is the SECOND stage of the compiler pipeline:

    Tokens --> [PARSER] --> AST (skeleton) --> Semantic Analysis (Phase 2) ...

Phase 1 scope:
  - Validate that the token stream matches RecipeLang's grammar
    (RECIPE header, INGREDIENT declarations, STEP calls).
  - Build a minimal AST (skeleton) representing the structure.
  - Report clear SYNTAX errors with line numbers.

NOT in Phase 1 scope (deliberately deferred to Phase 2):
  - Checking whether an ingredient used in a STEP was actually declared.
  - Checking for duplicate ingredient declarations.
  - Checking that quantities/time values are semantically valid (e.g. > 0).
  - Building the full symbol table.
  - Intermediate representation / execution.
"""

from lexer import tokenize, LexicalError


class SyntaxErrorRL(Exception):
    pass


# --- Minimal AST node classes (skeleton only for Phase 1) ------------------

class RecipeNode:
    def __init__(self, name):
        self.name = name
        self.ingredients = []   # list of IngredientNode
        self.steps = []         # list of StepNode

    def __repr__(self):
        return f"Recipe({self.name})"


class IngredientNode:
    def __init__(self, name, quantity, unit):
        self.name = name
        self.quantity = quantity
        self.unit = unit  # may be None (e.g. "tomato = 3")

    def __repr__(self):
        return f"Ingredient({self.name}={self.quantity}{' ' + self.unit if self.unit else ''})"


class StepNode:
    def __init__(self, action, args):
        self.action = action
        self.args = args  # list of raw arg tokens (identifiers / time values)

    def __repr__(self):
        return f"Step({self.action}, args={self.args})"


# --- Recursive-descent parser ----------------------------------------------

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, type_, value=None):
        tok = self.current()
        if tok.type != type_ or (value is not None and tok.value != value):
            expected = f"{type_} {value!r}" if value else type_
            raise SyntaxErrorRL(
                f"Syntax Error: expected {expected} but found "
                f"{tok.type} {tok.value!r} at line {tok.line}"
            )
        return self.advance()

    # <program> ::= <recipe>
    def parse_program(self):
        recipe = self.parse_recipe()
        self.expect("EOF")
        return recipe

    # <recipe> ::= "RECIPE" <identifier> <ingredient_list> <step_list>
    def parse_recipe(self):
        self.expect("KEYWORD", "RECIPE")
        name_tok = self.expect("IDENT")
        recipe = RecipeNode(name_tok.value)

        while self.current().type == "KEYWORD" and self.current().value == "INGREDIENT":
            recipe.ingredients.append(self.parse_ingredient())

        if not recipe.ingredients:
            raise SyntaxErrorRL(
                f"Syntax Error: recipe '{recipe.name}' has no INGREDIENT "
                f"declarations (at least one is required)"
            )

        while self.current().type == "KEYWORD" and self.current().value == "STEP":
            recipe.steps.append(self.parse_step())

        if not recipe.steps:
            raise SyntaxErrorRL(
                f"Syntax Error: recipe '{recipe.name}' has no STEP "
                f"statements (at least one is required)"
            )

        return recipe

    # <ingredient_decl> ::= "INGREDIENT" <identifier> "=" <number> [ <unit> ]
    def parse_ingredient(self):
        self.expect("KEYWORD", "INGREDIENT")
        name_tok = self.expect("IDENT")
        self.expect("ASSIGN")
        qty_tok = self.expect("NUMBER")

        unit = None
        if self.current().type == "UNIT":
            unit = self.advance().value

        return IngredientNode(name_tok.value, int(qty_tok.value), unit)

    # <step_stmt> ::= "STEP" <identifier> "(" [ <arg_list> ] ")"
    def parse_step(self):
        self.expect("KEYWORD", "STEP")
        action_tok = self.expect("IDENT")
        self.expect("LPAREN")

        args = []
        if self.current().type != "RPAREN":
            args.append(self.parse_arg())
            while self.current().type == "COMMA":
                self.advance()
                args.append(self.parse_arg())

        self.expect("RPAREN")
        return StepNode(action_tok.value, args)

    # <arg> ::= <identifier> | <number> <timeunit>
    def parse_arg(self):
        tok = self.current()
        if tok.type == "IDENT":
            self.advance()
            return ("ingredient_ref", tok.value)
        elif tok.type == "NUMBER":
            self.advance()
            unit_tok = self.expect("TIMEUNIT")
            return ("time_value", int(tok.value), unit_tok.value)
        else:
            raise SyntaxErrorRL(
                f"Syntax Error: invalid argument {tok.value!r} "
                f"at line {tok.line}"
            )


def parse_source(source: str) -> RecipeNode:
    """Convenience wrapper: source text -> validated skeleton AST."""
    tokens = tokenize(source)   # may raise LexicalError
    parser = Parser(tokens)
    return parser.parse_program()  # may raise SyntaxErrorRL


if __name__ == "__main__":
    src = open("sample_input.recipe").read()
    try:
        ast = parse_source(src)
        print(f"Syntax OK — Recipe '{ast.name}' parsed successfully.")
        print(f"Ingredients ({len(ast.ingredients)}):")
        for ing in ast.ingredients:
            print("   ", ing)
        print(f"Steps ({len(ast.steps)}):")
        for st in ast.steps:
            print("   ", st)
    except (LexicalError, SyntaxErrorRL) as e:
        print(e)
