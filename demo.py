"""
demo.py - Stage-by-stage demonstration of RecipeLang (for the review).

Run:   python demo.py sample_input.recipe
       python demo.py festival_rice.recipe --serves 8
Press Enter after each stage to move to the next one.
Use    --fast   to skip the pauses.
"""

import sys
from lexer import tokenize, LexicalError
from parser import parse_source, SyntaxErrorRL
from ast_visualizer import print_ast
from semantic_analyzer import SemanticAnalyzer
from ir_generator import generate_ir, format_ir_line
from interpreter import execute
from optimizer import (smart_warnings, optimize_ir, scale_ir,
                       total_cook_seconds, fmt_time)
from analysis import analyze_flow
from repair import try_repair, unparse
from expander import describe_call, describe_step
from nutrition import analyze_nutrition
from codegen import write_targets
import contracts
import smart
import subprocess

FAST = "--fast" in sys.argv
FIX = "--fix" in sys.argv
SMART = "--smart" in sys.argv
NOLEARN = "--no-learn" in sys.argv
MEM = smart.Memory() if SMART else None
TUNE_LIMIT = 0.5
if "--limit" in sys.argv:
    TUNE_LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) / 100


def banner(title, what, why):
    print("\n" + "=" * 64)
    print(f"  {title}")
    print("=" * 64)
    print(f"  WHAT IS HAPPENING : {what}")
    print(f"  WHY               : {why}")
    print("-" * 64)


def pause():
    if not FAST:
        input("\n  >> Press Enter for the next stage...")


def fmt_ing(name, info):
    unit = f" {info['unit']}" if info["unit"] else ""
    return f"{name}: {info['quantity']}{unit}"


def run(filepath, target_serves=None):
    source = open(filepath, "r").read()

    print("\n" + "#" * 64)
    print("  RecipeLang compiler - stage-by-stage demo")
    print("#" * 64)
    print("\n  INPUT (the recipe source code):\n")
    for i, line in enumerate(source.splitlines(), start=1):
        print(f"    {i:>2} | {line}")
    pause()

    # ---- Smart compiler (NEW) ----
    if SMART:
        banner("NEW: SMART COMPILER (reasoning, learning, adaptive, auto-fix)",
               "Before normal compilation the compiler detects and repairs errors on 3 levels,\n"
               "                      reasons about the recipe, learns from past recipes and adapts.",
               "An ordinary compiler stops at the first error. A smart one decides and repairs.")
        fixed_src, _smart_ast, smart_ok = smart.run_smart(source, MEM, learn=not NOLEARN)
        if not smart_ok:
            print("\n  Pipeline STOPPED: the smart compiler could not repair every problem.")
            return
        if fixed_src != source:
            source = fixed_src
            spath = filepath.rsplit(".", 1)[0] + "_smart.recipe"
            with open(spath, "w", encoding="utf-8") as f:
                f.write(source)
            print(f"\n  Corrected program saved to: {spath}")
            print("  The pipeline below continues with the CORRECTED program.")
        pause()

    # ---- Stage 1 ----
    banner("STAGE 1: LEXICAL ANALYSIS (Lexer)",
           "The source text is read character by character and split into tokens.",
           "The parser works on tokens, not raw text. Illegal characters are caught here.")
    try:
        tokens = tokenize(source)
    except LexicalError as e:
        print(f"  LEXICAL ERROR: {e}")
        print("\n  Pipeline STOPPED at Stage 1.")
        return
    print(f"  {'Token type':<14} {'Value':<12} Line")
    print(f"  {'-'*14} {'-'*12} ----")
    for t in tokens:
        print(f"  {str(t.type):<14} {str(t.value):<12} {t.line}")
    print(f"\n  RESULT: {len(tokens)} tokens generated.")
    pause()

    # ---- Stage 2 ----
    banner("STAGE 2: SYNTAX ANALYSIS (Parser)",
           "The tokens are checked against the RecipeLang grammar (recursive descent).",
           "It confirms the structure is valid: RECIPE, [SERVES], INGREDIENTs, then STEPs.")
    try:
        ast = parse_source(source)
    except SyntaxErrorRL as e:
        print(f"  SYNTAX ERROR: {e}")
        print("\n  Pipeline STOPPED at Stage 2.")
        return
    print("  RESULT: Syntax OK - the program follows the grammar. AST built.")
    pause()

    # ---- AST ----
    banner("AST: ABSTRACT SYNTAX TREE (Visualizer)",
           "The parser's tree is walked and printed as an ASCII tree.",
           "The AST keeps only the meaning of the program, not punctuation.")
    print_ast(ast)
    pause()

    # ---- Stage 3 ----
    banner("STAGE 3: SEMANTIC ANALYSIS",
           "The AST is checked for meaning (10 rules, listed below).",
           "A program can have correct grammar and still make no sense.")
    analyzer = SemanticAnalyzer(ast)
    symbol_table, errors = analyzer.analyze()
    print("  Rule 1: every ingredient used in a STEP is declared")
    print("  Rule 2: no ingredient is declared twice")
    print("  Rule 3: every quantity is greater than 0")
    print("  Rule 4: every cooking time is greater than 0")
    print("  Rule 5: SERVES (if present) is greater than 0")
    print("  Rule 6: REPEAT count (if present) is greater than 0")
    print("  Rule 7: DIET (if present) is known and no ingredient breaks it")
    print("  Rule 8: AVOID (if present) is a known allergen and no ingredient has it")
    print("  Rule 9: every ENSURE contract uses a known metric / operator / unit")
    print("  Rule 10: every PROTECT names a declared ingredient")
    print()
    if errors:
        print(f"  RESULT: {len(errors)} semantic error(s) found:")
        for err in errors:
            print(f"    - {err}")
        fixable = all("violates" in e.message for e in errors)
        if not (FIX and fixable):
            if fixable:
                print("\n  TIP: these errors can be repaired automatically. Run again with --fix")
            print("\n  Pipeline STOPPED at Stage 3 (IR is not generated for an invalid recipe).")
            return
        pause()
        # ---- Auto-repair (new) ----
        banner("NEW: AUTO-REPAIR (self-healing compiler)",
               "The compiler replaces each forbidden ingredient with a safe substitute\n"
               "                      everywhere in the program, then re-checks the result.",
               "Instead of only reporting the error, the compiler fixes it and proves the fix.")
        fixed_ast, changes = try_repair(ast)
        if fixed_ast is None:
            print("  Could not repair automatically:")
            for c in changes:
                print(f"    - {c}")
            print("\n  Pipeline STOPPED at Stage 3.")
            return
        for c in changes:
            print(f"  FIX: {c}")
        fixed_source = unparse(fixed_ast)
        print("\n  REPAIRED PROGRAM (RecipeLang source):\n")
        for i, line in enumerate(fixed_source.splitlines(), start=1):
            print(f"    {i:>2} | {line}")
        fixed_path = filepath.rsplit(".", 1)[0] + "_fixed.recipe"
        with open(fixed_path, "w", encoding="utf-8") as f:
            f.write(fixed_source)
        print(f"\n  Saved to: {fixed_path}")
        ast = fixed_ast
        analyzer = SemanticAnalyzer(ast)
        symbol_table, errors = analyzer.analyze()
        if errors:
            print("  Repaired program still has errors:")
            for err in errors:
                print(f"    - {err}")
            return
        print("  RE-CHECK: the repaired program passes all 10 semantic rules.")
    else:
        print("  RESULT: All 10 rules passed.")
    pause()

    # ---- Recipe contracts + auto-tuner (NOVELTY) ----
    if ast.contracts:
        banner("NOVELTY: RECIPE CONTRACTS + GOAL-DIRECTED AUTO-TUNER",
               "Each ENSURE goal is verified against the compiled recipe. If one fails, the\n"
               "                      compiler searches for the CHEAPEST edit that satisfies all goals.",
               "Design-by-contract for food: state the goal, let the compiler prove or fix it.")
        tuned = contracts.report(ast, TUNE_LIMIT,
                                 write_path=filepath.rsplit(".", 1)[0] + "_tuned.recipe")
        if tuned is None:
            print("\n  Pipeline STOPPED: the contracts cannot be met.")
            return
        if tuned is not ast:
            ast = tuned
            analyzer = SemanticAnalyzer(ast)
            symbol_table, errors = analyzer.analyze()
            if errors:
                print("  Tuned program has semantic errors:", errors)
                return
        pause()

    # ---- Procedure expansion (new) ----
    if ast.procedures:
        banner("NEW: PROCEDURE EXPANSION (inlining)",
               "Every CALL is replaced by the procedure's body, with each parameter\n"
               "                      substituted by the actual argument.",
               "Later stages then see only plain steps - no procedures at all.")
        for call, steps in ast.expansion_log:
            print(f"  {describe_call(call)}")
            for st in steps:
                print(f"      -> {describe_step(st)}")
        print(f"\n  RESULT: {len(ast.procedures)} procedure(s), "
              f"{len(ast.expansion_log)} call(s) expanded, "
              f"{len(ast.expanded_steps)} flat steps.")
        pause()

    # ---- Symbol table ----
    banner("SYMBOL TABLE",
           "Every declared ingredient is stored with its details.",
           "Later stages look up names here instead of re-reading the source.")
    print(f"  {'Name':<10} {'Type':<11} {'Qty':<5} {'Unit':<8} Scope")
    print(f"  {'-'*10} {'-'*11} {'-'*5} {'-'*8} {'-'*10}")
    for e in symbol_table.all_entries():
        print(f"  {e.name:<10} {e.type:<11} {e.quantity:<5} {(e.unit or '-'):<8} {e.scope}")
    for proc in ast.procedures:
        for prm in proc.params:
            print(f"  {prm:<10} {'PARAMETER':<11} {'-':<5} {'-':<8} {proc.name} (local)")
    pause()

    # ---- Smart warnings (new) ----
    banner("NEW: SMART WARNINGS",
           "Checks that go beyond errors: the recipe is valid, but is it sensible?",
           "Real compilers also warn about suspicious code, not only wrong code.")
    warns = smart_warnings(ast)
    if warns:
        for w in warns:
            print(f"  WARNING: {w}")
    else:
        print("  No warnings - the recipe looks sensible.")
    pause()

    # ---- Stage 4 ----
    banner("STAGE 4: INTERMEDIATE CODE GENERATION (IR)",
           "The tree is flattened into numbered instructions. Ingredient names are\n"
           "                      replaced by real quantities. REPEAT n is UNROLLED into n steps.",
           "A flat list is simple to execute, e.g. add(oil) becomes add(oil=2 tbsp).")
    ir = generate_ir(ast, symbol_table)
    for instr in ir:
        print(format_ir_line(instr))
    print(f"\n  RESULT: {len(ir)} IR instructions generated.")
    pause()

    # ---- Optimizer (new) ----
    banner("NEW: IR OPTIMIZER",
           "Redundant instructions are removed or merged before execution.",
           "A shorter IR runs faster. This is the code optimization phase.")
    if SMART:
        opt, changes, _info = smart.smart_optimize(ir, MEM, learn=False)
    else:
        opt, changes = optimize_ir(ir)
    if changes:
        for c in changes:
            print(f"  - {c}")
    else:
        print("  - none needed (the IR is already minimal)")
    print("\n  IR AFTER optimization:")
    for instr in opt:
        print(format_ir_line(instr))
    print(f"\n  RESULT: {len(ir)} instructions -> {len(opt)} instructions")
    print(f"  Total cooking time: {fmt_time(total_cook_seconds(opt))}")
    pause()

    # ---- Kitchen data-flow analysis (new) ----
    banner("NEW: KITCHEN DATA-FLOW ANALYSIS",
           "The IR is walked in order while a kitchen state (pan hot/cold, contents,\n"
           "                      cooked, served) is carried along and checked at every step.",
           "Unlike the semantic rules, this checks the ORDER of the steps (flow-sensitive).")
    flow_errors, flow_warnings, trace = analyze_flow(opt)
    for n, act, state in trace:
        print(f"  [{n}] {act:<9} {state}")
    print()
    for w in flow_warnings:
        print(f"  WARNING: {w}")
    if flow_errors:
        for e in flow_errors:
            print(f"  FLOW ERROR: {e}")
        print(f"\n  RESULT: {len(flow_errors)} flow error(s). Pipeline STOPPED before execution.")
        return
    print("  RESULT: the order of steps is valid.")
    pause()

    # ---- Nutrition & allergen analysis (new) ----
    banner("NEW: NUTRITION & ALLERGEN ANALYSIS",
           "The ingredient knowledge base is used to compute calories and to list\n"
           "                      the allergen / diet tags found in the recipe.",
           "The compiler uses domain knowledge, not just syntax, to analyze the program.")
    rows, total_kcal, per_serving, tag_list, unknown = analyze_nutrition(opt, ast.serves)
    print(f"  {'Ingredient':<10} {'Amount':<10} {'kcal':<8} Tags")
    print(f"  {'-'*10} {'-'*10} {'-'*8} {'-'*12}")
    for name, qty, unit, kcal, tags in rows:
        amt = f"{qty} {unit}" if unit else f"{qty}"
        print(f"  {name:<10} {amt:<10} {('?' if kcal is None else round(kcal)):<8} {', '.join(tags) or '-'}")
    print(f"\n  Total calories      : {total_kcal} kcal")
    if per_serving is not None:
        print(f"  Calories per serving: {per_serving} kcal (SERVES {ast.serves})")
    print(f"  Allergen/diet tags  : {', '.join(tag_list) if tag_list else 'none'}")
    if ast.diet or ast.avoid:
        decl = ([f"DIET {ast.diet}"] if ast.diet else []) + [f"AVOID {a}" for a in ast.avoid]
        print(f"  Declared constraints: {', '.join(decl)}  -> all satisfied")
    if unknown:
        print(f"  (not in knowledge base: {', '.join(unknown)})")
    pause()

    # ---- Scaling (new) ----
    final_ir = opt
    if ast.serves is not None and target_serves is not None:
        factor = target_serves / ast.serves
        factor = int(factor) if factor == int(factor) else round(factor, 2)
        banner(f"NEW: COMPILE-TIME SCALING (SERVES {ast.serves} -> {target_serves})",
               f"Every ingredient quantity in the IR is multiplied by {factor}.",
               "The recipe adapts to a new number of servings without editing the source.")
        final_ir = scale_ir(opt, factor)
        for instr in final_ir:
            print(format_ir_line(instr))
        pause()
    elif target_serves is not None:
        print("\n  (Scaling skipped: this recipe has no SERVES line.)")

    # ---- Stage 5 ----
    banner("STAGE 5: INTERPRETER / EXECUTION ENGINE",
           "The final IR instructions are executed one by one.",
           "The runtime environment records how much of each ingredient is used.")
    env, log = execute(final_ir)
    for line in log:
        print(line)
    print("\n  Runtime environment - ingredient usage:")
    for name, info in env.used_ingredients.items():
        print(f"    {fmt_ing(name, info)}")
    pause()

    # ---- Stage 6: target code generation (new) ----
    banner("STAGE 6: TARGET CODE GENERATION (back end)",
           "The final IR is translated into two real target programs: a Python\n"
           "                      program and an HTML recipe card.",
           "A compiler's last job: produce code in another language that runs on its own.")
    py_path, html_path = write_targets(ast.name, final_ir)
    print(f"  Generated: {py_path}")
    print(f"  Generated: {html_path}   (open it in a browser)")
    print("\n  --- contents of the generated Python program ---")
    for line in open(py_path, encoding="utf-8").read().splitlines():
        print(f"  | {line}")
    print("\n  --- running the generated program ---")
    out = subprocess.run([sys.executable, py_path], capture_output=True, text=True)
    for line in out.stdout.splitlines():
        print(f"  > {line}")
    pause()

    print("\n" + "#" * 64)
    print("  Recipe compiled and executed successfully.")
    print("#" * 64)


if __name__ == "__main__":
    args = sys.argv[1:]
    serves = None
    if "--serves" in args:
        serves = int(args[args.index("--serves") + 1])
    files = [a for i, a in enumerate(args)
             if not a.startswith("--") and not (i > 0 and args[i - 1] in ("--serves", "--limit"))]
    run(files[0] if files else "sample_input.recipe", serves)
