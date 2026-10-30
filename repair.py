"""
repair.py - RecipeLang AUTO-REPAIR ("self-healing compiler")

Normal compilers stop at an error. RecipeLang can also REPAIR the program.

When a recipe breaks a DIET / AVOID constraint, this pass:
  1. finds every ingredient whose tags violate the constraint,
  2. replaces it with the safe substitute from the knowledge base
     (in the declarations AND in every STEP / CALL / procedure body),
  3. merges it into an existing ingredient if the substitute is already declared,
  4. prints the corrected program as RecipeLang source (unparse),
  5. the caller re-runs the semantic analyzer to PROVE the repaired program is valid.

This is "error recovery" taken one step further than skipping tokens:
the compiler fixes the program and verifies the fix.
"""

import copy
from parser import CallNode
from knowledge import KB, DIETS, ALLERGENS, tags_of


def forbidden_tags(recipe):
    forbidden = set()
    if recipe.diet in DIETS:
        forbidden |= DIETS[recipe.diet]
    for a in recipe.avoid:
        if a in ALLERGENS:
            forbidden.add(a)
    return forbidden


def _rename_arg(arg, mapping):
    if arg[0] == "ingredient_ref" and arg[1] in mapping:
        return ("ingredient_ref", mapping[arg[1]])
    return arg


def try_repair(recipe):
    """Returns (new_recipe, changes) or (None, reasons) if it cannot be repaired."""
    forbidden = forbidden_tags(recipe)
    mapping, reasons = {}, []
    for ing in recipe.ingredients:
        bad = sorted(tags_of(ing.name) & forbidden)
        if not bad:
            continue
        sub = KB[ing.name]["sub"]
        if not sub:
            reasons.append(f"no safe substitute known for '{ing.name}'")
        elif tags_of(sub) & forbidden:
            reasons.append(f"substitute '{sub}' for '{ing.name}' is also forbidden")
        else:
            mapping[ing.name] = sub
    if reasons or not mapping:
        return None, reasons or ["nothing to repair"]

    new = copy.deepcopy(recipe)
    changes = []
    # declarations (merge with an existing declaration of the substitute)
    result = []
    for ing in new.ingredients:
        if ing.name in mapping:
            sub = mapping[ing.name]
            existing = next((i for i in result + new.ingredients
                             if i.name == sub and i is not ing), None)
            if existing is not None:
                if existing.unit != ing.unit:
                    return None, [f"cannot merge '{ing.name}' into '{sub}': different units"]
                existing.quantity += ing.quantity
                changes.append(f"merged '{ing.name}' into existing '{sub}'")
                continue
            changes.append(f"replaced ingredient '{ing.name}' with '{sub}'")
            ing.name = sub
        result.append(ing)
    new.ingredients = result

    def fix_nodes(nodes):
        for node in nodes:
            node.args = [_rename_arg(a, mapping) for a in node.args]

    fix_nodes(new.steps)
    for p in new.procedures:
        fix_nodes(p.body)
    return new, changes


def _arg(a):
    return a[1] if a[0] == "ingredient_ref" else f"{a[1]} {a[2]}"


def _step_line(node):
    rep = f"REPEAT {node.repeat} " if node.repeat != 1 else ""
    args = ", ".join(_arg(a) for a in node.args)
    if isinstance(node, CallNode):
        return f"{rep}CALL {node.name}({args})"
    return f"{rep}STEP {node.action}({args})"


def unparse(recipe):
    """AST -> RecipeLang source text (the inverse of the parser)."""
    lines = [f"RECIPE {recipe.name}"]
    if recipe.serves is not None:
        lines.append(f"SERVES {recipe.serves}")
    if recipe.diet:
        lines.append(f"DIET {recipe.diet}")
    for a in recipe.avoid:
        lines.append(f"AVOID {a}")
    for name in getattr(recipe, "protect", []):
        lines.append(f"PROTECT {name}")
    for c in getattr(recipe, "contracts", []):
        unit = f" {c.unit}" if c.unit else ""
        lines.append(f"ENSURE {c.metric} {c.op} {c.value}{unit}")
    for ing in recipe.ingredients:
        unit = f" {ing.unit}" if ing.unit else ""
        lines.append(f"INGREDIENT {ing.name} = {ing.quantity}{unit}")
    for p in recipe.procedures:
        lines.append("")
        lines.append(f"DEFINE {p.name}({', '.join(p.params)})")
        for node in p.body:
            lines.append("  " + _step_line(node))
        lines.append("END")
    lines.append("")
    for node in recipe.steps:
        lines.append(_step_line(node))
    return "\n".join(lines) + "\n"
