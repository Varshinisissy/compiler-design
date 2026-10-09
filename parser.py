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
        self.serves = None      # optional: SERVES <n> (base number of servings)
        self.diet = None        # optional: DIET <vegetarian|vegan>
        self.avoid = []         # optional: AVOID <allergen> (repeatable)
        self.procedures = []    # list of ProcNode (DEFINE ... END)

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
    def __init__(self, action, args, repeat=1):
        self.action = action
        self.args = args  # list of raw arg tokens (identifiers / time values)
        self.repeat = repeat  # optional: REPEAT <n> STEP ... (default 1)
        self.origin = None    # name of the procedure this step came from (after expansion)

    def __repr__(self):
        return f"Step({self.action}, args={self.args})"


class ProcNode:
    """DEFINE name(params) ... END  - a reusable procedure (like a function)."""
    def __init__(self, name, params, body):
        self.name = name
        self.params = params   # list of parameter names
        self.body = body       # list of StepNode / CallNode


class CallNode:
    """CALL name(args) - use of a procedure (replaced by its body at compile time)."""
    def __init__(self, name, args, repeat=1):
        self.name = name
        self.args = args
        self.repeat = repeat


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

        # optional header lines, in any order:
        #   "SERVES" <number> | "DIET" <identifier> | "AVOID" <identifier>
        while self.current().type == "KEYWORD" and self.current().value in ("SERVES", "DIET", "AVOID"):
            kw = self.advance().value
            if kw == "SERVES":
                recipe.serves = int(self.expect("NUMBER").value)
            elif kw == "DIET":
                recipe.diet = self.expect("IDENT").value
            else:
                recipe.avoid.append(self.expect("IDENT").value)

        while self.current().type == "KEYWORD" and self.current().value == "INGREDIENT":
            recipe.ingredients.append(self.parse_ingredient())

        if not recipe.ingredients:
            raise SyntaxErrorRL(
                f"Syntax Error: recipe '{recipe.name}' has no INGREDIENT "
                f"declarations (at least one is required)"
            )

        while self.current().type == "KEYWORD" and self.current().value == "DEFINE":
            recipe.procedures.append(self.parse_define())

        while self.current().type == "KEYWORD" and self.current().value in ("STEP", "REPEAT", "CALL"):
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

    # <procedure> ::= "DEFINE" <identifier> "(" [ <identifier> { "," <identifier> } ] ")"
    #                 <step_stmt> { <step_stmt> } "END"
    def parse_define(self):
        self.expect("KEYWORD", "DEFINE")
        name_tok = self.expect("IDENT")
        self.expect("LPAREN")
        params = []
        if self.current().type != "RPAREN":
            params.append(self.expect("IDENT").value)
            while self.current().type == "COMMA":
                self.advance()
                params.append(self.expect("IDENT").value)
        self.expect("RPAREN")

        body = []
        while self.current().type == "KEYWORD" and self.current().value in ("STEP", "REPEAT", "CALL"):
            body.append(self.parse_step())
        if not body:
            raise SyntaxErrorRL(
                f"Syntax Error: procedure '{name_tok.value}' has an empty body "
                f"(at least one STEP or CALL is required)"
            )
        self.expect("KEYWORD", "END")
        return ProcNode(name_tok.value, params, body)

    # <arg_list> ::= "(" [ <arg> { "," <arg> } ] ")"
    def parse_arglist(self):
        self.expect("LPAREN")
        args = []
        if self.current().type != "RPAREN":
            args.append(self.parse_arg())
            while self.current().type == "COMMA":
                self.advance()
                args.append(self.parse_arg())
        self.expect("RPAREN")
        return args

    # <step_stmt> ::= [ "REPEAT" <number> ] ( "STEP" <identifier> <arg_list>
    #                                       | "CALL" <identifier> <arg_list> )
    def parse_step(self):
        repeat = 1
        if self.current().type == "KEYWORD" and self.current().value == "REPEAT":
            self.advance()
            repeat = int(self.expect("NUMBER").value)
        if self.current().type == "KEYWORD" and self.current().value == "CALL":
            self.advance()
            name_tok = self.expect("IDENT")
            return CallNode(name_tok.value, self.parse_arglist(), repeat)
        self.expect("KEYWORD", "STEP")
        action_tok = self.expect("IDENT")
        return StepNode(action_tok.value, self.parse_arglist(), repeat)

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
