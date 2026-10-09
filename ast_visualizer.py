"""
ast_visualizer.py — RecipeLang Phase 2 AST Visualization

Satisfies the manual's "Abstract Syntax Tree: AST construction,
TRAVERSAL, and VISUALIZATION" requirement. parser.py already handles
construction (building RecipeNode/IngredientNode/StepNode objects);
this module TRAVERSES that tree and prints it as a readable ASCII
diagram, in the same style used in Section 15 of the design document.
"""

from parser import RecipeNode, CallNode


def _arg_text(arg):
    if arg[0] == "ingredient_ref":
        return f"Ref({arg[1]})"
    return f"Time({arg[1]}, {arg[2]})"


def _step_text(step):
    args_str = ", ".join(_arg_text(a) for a in step.args)
    rep = f", repeat={step.repeat}" if step.repeat != 1 else ""
    if isinstance(step, CallNode):
        return f"Call(name={step.name}, args=[{args_str}]{rep})"
    return f"Step(action={step.action}, args=[{args_str}]{rep})"


def print_ast(recipe: RecipeNode):
    """Traverses the AST and prints it as an ASCII tree."""
    serves = f", serves={recipe.serves}" if recipe.serves is not None else ""
    extra = ""
    if recipe.diet:
        extra += f", diet={recipe.diet}"
    if recipe.avoid:
        extra += f", avoid={'+'.join(recipe.avoid)}"
    print(f"Recipe({recipe.name}{serves}{extra})")

    print("├── IngredientList")
    for i, ing in enumerate(recipe.ingredients):
        is_last = i == len(recipe.ingredients) - 1
        connector = "└──" if is_last else "├──"
        unit_str = f"unit={ing.unit}" if ing.unit else "unit=None"
        print(f"│   {connector} Ingredient(name={ing.name}, qty={ing.quantity}, {unit_str})")

    if recipe.procedures:
        print("├── ProcedureList")
        for i, proc in enumerate(recipe.procedures):
            last_proc = i == len(recipe.procedures) - 1
            pconn = "└──" if last_proc else "├──"
            pad = "    " if last_proc else "│   "
            print(f"│   {pconn} Procedure(name={proc.name}, params=[{', '.join(proc.params)}])")
            for j, step in enumerate(proc.body):
                sconn = "└──" if j == len(proc.body) - 1 else "├──"
                print(f"│   {pad}{sconn} {_step_text(step)}")

    print("└── StepList")
    for i, step in enumerate(recipe.steps):
        is_last = i == len(recipe.steps) - 1
        connector = "└──" if is_last else "├──"
        print(f"    {connector} {_step_text(step)}")
