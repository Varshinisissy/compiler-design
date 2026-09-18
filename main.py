"""
main.py — RecipeLang Phase 1 Prototype Driver

Runs the pipeline implemented so far:

    Source Code (.recipe file)
          |
          v
      [ LEXER ]  ->  Tokens
          |
          v
      [ PARSER ] ->  Skeleton AST + Syntax Validation
          |
          v
      Structured Summary Output   (Phase 1 stops here)

Phase 2 will add: Semantic Analysis + full Symbol Table.
Phase 3 will add: Intermediate Representation + Interpreter/Execution.
"""

import sys
from lexer import tokenize, LexicalError
from parser import parse_source, SyntaxErrorRL


def run(filepath: str):
    with open(filepath, "r") as f:
        source = f.read()

    print("=" * 60)
    print(f"RecipeLang Phase 1 Prototype — processing '{filepath}'")
    print("=" * 60)

    # ---- Stage 1: Lexical Analysis -----------------------------------
    print("\n[Stage 1] Lexical Analysis")
    try:
        tokens = tokenize(source)
    except LexicalError as e:
        print(e)
        return

    print(f"  Total tokens generated: {len(tokens)}")
    print("  Token stream:")
    for tok in tokens:
        if tok.type != "EOF":
            print(f"    {tok.type:<10} {tok.value!r:<15} (line {tok.line})")

    # ---- Stage 2: Syntax Analysis --------------------------------------
    print("\n[Stage 2] Syntax Analysis (Parsing)")
    try:
        ast = parse_source(source)
    except SyntaxErrorRL as e:
        print(f"  {e}")
        return

    print("  Syntax OK — input matches RecipeLang grammar.")

    # ---- Stage 3: Structured Output (Phase 1 "meaningful output") -----
    print("\n[Stage 3] Structured Recipe Summary (Phase 1 output)")
    print(f"  Recipe Name : {ast.name}")
    print(f"  Ingredients : {len(ast.ingredients)}")
    for ing in ast.ingredients:
        unit_str = f" {ing.unit}" if ing.unit else ""
        print(f"    - {ing.name}: {ing.quantity}{unit_str}")
    print(f"  Steps       : {len(ast.steps)}")
    for i, st in enumerate(ast.steps, start=1):
        arg_strs = []
        for arg in st.args:
            if arg[0] == "ingredient_ref":
                arg_strs.append(arg[1])
            else:
                arg_strs.append(f"{arg[1]} {arg[2]}")
        print(f"    {i}. {st.action}({', '.join(arg_strs)})")

    print("\nNote: Ingredient-existence checks, duplicate-declaration checks,")
    print("and quantity/time validity checks are SEMANTIC ANALYSIS tasks —")
    print("planned for Phase 2, not implemented in this Phase 1 prototype.")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "sample_input.recipe"
    run(filepath)
