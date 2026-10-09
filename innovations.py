"""
innovations.py - RecipeLang "smart compiler" extras (works on top of Phase 2).

 1. SMART WARNINGS      : lint-style checks that go beyond the 4 semantic rules
 2. IR OPTIMIZER        : merges / removes redundant instructions (before vs after)
 3. COOKING TIME REPORT : total cooking time computed from the IR
 4. RECIPE SCALING      : rewrites the IR for a different number of servings

Run:   python innovations.py sample_input.recipe
       python innovations.py sample_input.recipe --scale 2
       python innovations.py sample_input.recipe --fast     (no pauses)
"""

import sys
import copy
from lexer import tokenize
from parser import parse_source
from semantic_analyzer import SemanticAnalyzer
from ir_generator import generate_ir, format_ir_line, IRInstruction
from interpreter import execute

FAST = "--fast" in sys.argv
TO_SECONDS = {"second": 1, "seconds": 1, "minute": 60, "minutes": 60,
              "hour": 3600, "hours": 3600}


def banner(title, what):
    print("\n" + "=" * 64)
    print(f"  {title}")
    print("=" * 64)
    print(f"  WHAT IS HAPPENING : {what}")
    print("-" * 64)


def pause():
    if not FAST:
        input("\n  >> Press Enter for the next feature...")


# ---------------------------------------------------------------- 1. warnings
def smart_warnings(ast):
    warnings = []
    used = set()
    seen_add = set()
    added_anything = False
    for step in ast.steps:
        for arg in step.args:
            if arg[0] == "ingredient_ref":
                used.add(arg[1])
        if step.action == "add":
            for arg in step.args:
                if arg[0] == "ingredient_ref":
                    if arg[1] in seen_add:
                        warnings.append(f"ingredient '{arg[1]}' is added more than once")
                    seen_add.add(arg[1])
            added_anything = True
        if step.action == "cook" and not added_anything:
            warnings.append("cook() is used before anything was added to the pan")
    for ing in ast.ingredients:
        if ing.name not in used:
            warnings.append(f"ingredient '{ing.name}' is declared but never used")
    actions = [s.action for s in ast.steps]
    if "serve" not in actions:
        warnings.append("recipe has no serve() step")
    elif actions[-1] != "serve":
        warnings.append("serve() is not the last step")
    return warnings


# --------------------------------------------------------------- 2. optimizer
def optimize_ir(ir):
    """Returns (new_ir, list_of_changes)."""
    changes = []
    out = []
    for instr in ir:
        prev = out[-1] if out else None
        # Rule A: two identical argument-less steps in a row -> keep one
        if (prev is not None and not instr.resolved_args and not prev.resolved_args
                and prev.action == instr.action):
            changes.append(f"removed duplicate {instr.action}() (step {instr.index})")
            continue
        # Rule B: two cook() steps in a row with the same unit -> merge times
        if (prev is not None and instr.action == "cook" and prev.action == "cook"
                and len(prev.resolved_args) == 1 and len(instr.resolved_args) == 1
                and prev.resolved_args[0]["unit"] == instr.resolved_args[0]["unit"]):
            prev.resolved_args[0]["duration"] += instr.resolved_args[0]["duration"]
            changes.append(f"merged cook steps {prev.index} and {instr.index} "
                           f"-> cook({prev.resolved_args[0]['duration']} "
                           f"{prev.resolved_args[0]['unit']})")
            continue
        out.append(copy.deepcopy(instr))
    for i, instr in enumerate(out, start=1):
        instr.index = i
    return out, changes


# ------------------------------------------------------------- 3. time report
def total_cook_seconds(ir):
    total = 0
    for instr in ir:
        for arg in instr.resolved_args:
            if arg["kind"] == "time":
                total += arg["duration"] * TO_SECONDS[arg["unit"]]
    return total


def fmt_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    parts = []
    if h:
        parts.append(f"{h} hour(s)")
    if m:
        parts.append(f"{m} minute(s)")
    if s or not parts:
        parts.append(f"{s} second(s)")
    return " ".join(parts)


# ---------------------------------------------------------------- 4. scaling
def scale_ir(ir, factor):
    scaled = copy.deepcopy(ir)
    for instr in scaled:
        for arg in instr.resolved_args:
            if arg["kind"] == "ingredient":
                q = arg["quantity"] * factor
                arg["quantity"] = int(q) if q == int(q) else round(q, 2)
    return scaled


def main(filepath, factor):
    source = open(filepath).read()
    tokenize(source)
    ast = parse_source(source)
    table, errors = SemanticAnalyzer(ast).analyze()
    if errors:
        print("Semantic errors found - fix them first:")
        for e in errors:
            print("  -", e)
        return
    ir = generate_ir(ast, table)

    print("\n" + "#" * 64)
    print(f"  RecipeLang smart-compiler extras  -  {ast.name}")
    print("#" * 64)

    # 1
    banner("FEATURE 1: SMART WARNINGS",
           "Checks that go beyond errors: the recipe is valid, but is it sensible?")
    warns = smart_warnings(ast)
    if warns:
        for w in warns:
            print(f"  WARNING: {w}")
    else:
        print("  No warnings - the recipe looks sensible.")
    pause()

    # 2
    banner("FEATURE 2: IR OPTIMIZER",
           "Redundant instructions are removed or merged before execution.")
    print("  IR BEFORE optimization:")
    for i in ir:
        print(format_ir_line(i))
    opt, changes = optimize_ir(ir)
    print("\n  Optimizations applied:")
    if changes:
        for c in changes:
            print(f"    - {c}")
    else:
        print("    - none needed (the IR is already minimal)")
    print("\n  IR AFTER optimization:")
    for i in opt:
        print(format_ir_line(i))
    print(f"\n  RESULT: {len(ir)} instructions -> {len(opt)} instructions")
    pause()

    # 3
    banner("FEATURE 3: COOKING TIME REPORT",
           "Cook times from the optimized IR are converted to seconds and added up.")
    secs = total_cook_seconds(opt)
    print(f"  Total cooking time: {fmt_time(secs)}  ({secs} seconds)")
    pause()

    # 4
    banner(f"FEATURE 4: RECIPE SCALING (x{factor})",
           "Every ingredient quantity in the IR is multiplied by the scale factor.")
    scaled = scale_ir(opt, factor)
    for i in scaled:
        print(format_ir_line(i))
    env, _ = execute(scaled)
    print(f"\n  Shopping list for x{factor}:")
    for name, info in env.used_ingredients.items():
        unit = f" {info['unit']}" if info["unit"] else ""
        print(f"    {name}: {info['quantity']}{unit}")

    print("\n" + "#" * 64)
    print("  Extras finished.")
    print("#" * 64)


if __name__ == "__main__":
    args = sys.argv[1:]
    factor = 2
    if "--scale" in args:
        factor = float(args[args.index("--scale") + 1])
        factor = int(factor) if factor == int(factor) else factor
    files = [a for i, a in enumerate(args)
             if not a.startswith("--") and not (i > 0 and args[i - 1] == "--scale")]
    main(files[0] if files else "sample_input.recipe", factor)
