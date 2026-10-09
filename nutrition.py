"""
nutrition.py - RecipeLang NUTRITION & ALLERGEN ANALYSIS

Uses the ingredient knowledge base to compute, from the final IR:
  - calories per ingredient and in total
  - calories per serving (if the recipe declares SERVES)
  - which allergen / diet tags appear in the recipe
"""

from knowledge import kcal_of, tags_of


def analyze_nutrition(ir, serves=None):
    used = {}
    for instr in ir:
        for a in instr.resolved_args:
            if a["kind"] == "ingredient":
                e = used.setdefault(a["name"], [0, a["unit"]])
                e[0] += a["quantity"]
    rows, total, unknown = [], 0, []
    tags = set()
    for name, (qty, unit) in used.items():
        kcal = kcal_of(name, qty, unit)
        t = tags_of(name)
        tags |= t
        if kcal is None:
            unknown.append(name)
        else:
            total += kcal
        rows.append((name, qty, unit, kcal, sorted(t)))
    per_serving = round(total / serves) if serves else None
    return rows, round(total), per_serving, sorted(tags), unknown
