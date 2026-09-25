"""
ast_visualizer.py — RecipeLang Phase 2 AST Visualization
"""

from parser import RecipeNode


def print_ast(recipe: RecipeNode):
    """Traverses the AST and prints it as an ASCII tree."""
    print(f"Recipe({recipe.name})")

    print("├── IngredientList")
    for i, ing in enumerate(recipe.ingredients):
        is_last = i == len(recipe.ingredients) - 1
        connector = "└──" if is_last else "├──"
        unit_str = f"unit={ing.unit}" if ing.unit else "unit=None"
        print(f"│   {connector} Ingredient(name={ing.name}, qty={ing.quantity}, {unit_str})")

    print("└── StepList")
    for i, step in enumerate(recipe.steps):
        is_last = i == len(recipe.steps) - 1
        connector = "└──" if is_last else "├──"
        arg_reprs = []
        for arg in step.args:
            if arg[0] == "ingredient_ref":
                arg_reprs.append(f"Ref({arg[1]})")
            else:
                arg_reprs.append(f"Time({arg[1]}, {arg[2]})")
        args_str = ", ".join(arg_reprs) if arg_reprs else ""
        print(f"    {connector} Step(action={step.action}, args=[{args_str}])")