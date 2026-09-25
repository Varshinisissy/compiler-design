"""
main.py — RecipeLang Phase 2 Prototype Driver (FULL Phase 2 pipeline)
"""

import sys
from lexer import tokenize, LexicalError
from parser import parse_source, SyntaxErrorRL
from ast_visualizer import print_ast
from semantic_analyzer import SemanticAnalyzer
from ir_generator import generate_ir, format_ir_line
from interpreter import execute


def run(filepath: str):
    source = open(filepath, "r").read()

    print("=" * 60)
    print(f"RecipeLang Phase 2 Prototype — processing '{filepath}'")
    print("=" * 60)

    print("\n[Stage 1] Lexical Analysis")
    try:
        tokens = tokenize(source)
    except LexicalError as e:
        print(f"  {e}")
        return
    print(f"  Total tokens generated: {len(tokens)}")

    print("\n[Stage 2] Syntax Analysis (Parsing)")
    try:
        ast = parse_source(source)
    except SyntaxErrorRL as e:
        print(f"  {e}")
        return
    print("  Syntax OK — input matches RecipeLang grammar.")

    print("\n[AST] Abstract Syntax Tree")
    print_ast(ast)

    print("\n[Stage 3] Semantic Analysis")
    analyzer = SemanticAnalyzer(ast)
    symbol_table, errors = analyzer.analyze()

    if errors:
        print(f"  {len(errors)} semantic error(s) found:")
        for err in errors:
            print(f"    - {err}")
        print("\n  Compilation stopped. Fix the semantic errors above and re-run.")
        return
    print("  Semantic OK — all ingredient references and values are valid.")

    print("\n[Symbol Table]")
    print(f"  {'Name':<10} {'Type':<11} {'Qty':<5} {'Unit':<8} Scope")
    print(f"  {'-'*10} {'-'*11} {'-'*5} {'-'*8} {'-'*10}")
    for entry in symbol_table.all_entries():
        unit_str = entry.unit if entry.unit else "-"
        print(f"  {entry.name:<10} {entry.type:<11} {entry.quantity:<5} {unit_str:<8} {entry.scope}")

    print("\n[Stage 4] Intermediate Representation (IR)")
    ir = generate_ir(ast, symbol_table)
    for instr in ir:
        print(format_ir_line(instr))

    print("\n[Stage 5] Interpreter / Execution Engine")
    env, log = execute(ir)
    for line in log:
        print(line)

    print("\n[Runtime Environment] Total ingredient usage after execution")
    for name, info in env.used_ingredients.items():
        unit_str = f" {info['unit']}" if info["unit"] else ""
        print(f"  {name}: {info['quantity']}{unit_str} used")

    print("\n[Final Output] Structured Recipe Summary")
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

    print("\nRecipe compiled and executed successfully.")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "sample_input.recipe"
    run(filepath)