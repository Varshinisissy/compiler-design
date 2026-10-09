"""
optimizer.py - RecipeLang smart-compiler passes (run after IR generation).

  smart_warnings(ast)   : lint checks beyond the semantic errors
  optimize_ir(ir)       : removes duplicate steps, merges consecutive cooks
  total_cook_seconds(ir): total cooking time
  scale_ir(ir, factor)  : rewrites quantities for a different number of servings
"""

import copy

# Steps that are pointless to do twice in a row (doing them again changes nothing).
IDEMPOTENT = {"heat_pan", "preheat"}
TO_SECONDS = {"second": 1, "seconds": 1, "minute": 60, "minutes": 60,
              "hour": 3600, "hours": 3600}


# ---------------------------------------------------------------- 1. warnings
def smart_warnings(ast):
    warnings = []
    used = set()
    seen_add = set()
    added_anything = False
    steps = getattr(ast, "expanded_steps", ast.steps)
    for step in steps:
        for arg in step.args:
            if arg[0] == "ingredient_ref":
                used.add(arg[1])
        if step.action == "add":
            for arg in step.args:
                if arg[0] == "ingredient_ref":
                    if arg[1] in seen_add or step.repeat > 1:
                        warnings.append(f"ingredient '{arg[1]}' is added more than once")
                    seen_add.add(arg[1])
            added_anything = True
        if step.action == "cook" and not added_anything:
            warnings.append("cook() is used before anything was added to the pan")
    called = {n.name for n in ast.steps if not hasattr(n, "action")}
    for p in getattr(ast, "procedures", []):
        called |= {n.name for n in p.body if not hasattr(n, "action")}
    for p in getattr(ast, "procedures", []):
        if p.name not in called:
            warnings.append(f"procedure '{p.name}' is defined but never called")
    for ing in ast.ingredients:
        if ing.name not in used:
            warnings.append(f"ingredient '{ing.name}' is declared but never used")
    actions = [s.action for s in steps]
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
        # Rule A: a repeated idempotent step (e.g. heat_pan twice) -> keep one
        if (prev is not None and instr.action in IDEMPOTENT and not instr.resolved_args
                and not prev.resolved_args and prev.action == instr.action):
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
