"""
semantic_analyzer.py — RecipeLang Phase 2 Semantic Analyzer + Symbol Table
"""

from parser import RecipeNode


class SemanticError:
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return self.message


class SymbolTableEntry:
    def __init__(self, name, type_, quantity, unit, scope):
        self.name = name
        self.type = type_
        self.quantity = quantity
        self.unit = unit
        self.scope = scope


class SymbolTable:
    def __init__(self):
        self.entries = {}

    def declare(self, name, type_, quantity, unit, scope):
        self.entries[name] = SymbolTableEntry(name, type_, quantity, unit, scope)

    def exists(self, name):
        return name in self.entries

    def lookup(self, name):
        return self.entries.get(name)

    def all_entries(self):
        return list(self.entries.values())


class SemanticAnalyzer:
    def __init__(self, recipe: RecipeNode):
        self.recipe = recipe
        self.symbol_table = SymbolTable()
        self.errors = []

    def analyze(self):
        self._check_ingredients()
        self._check_steps()
        return self.symbol_table, self.errors

    def _check_ingredients(self):
        for ing in self.recipe.ingredients:
            if self.symbol_table.exists(ing.name):
                self.errors.append(SemanticError(
                    f"Semantic Error: ingredient '{ing.name}' is declared more than "
                    f"once in recipe '{self.recipe.name}'"
                ))
                continue

            if ing.quantity <= 0:
                self.errors.append(SemanticError(
                    f"Semantic Error: ingredient '{ing.name}' has an invalid "
                    f"quantity ({ing.quantity}) — quantity must be a positive number"
                ))

            self.symbol_table.declare(
                ing.name, "INGREDIENT", ing.quantity, ing.unit, self.recipe.name
            )

    def _check_steps(self):
        for step in self.recipe.steps:
            for arg in step.args:
                if arg[0] == "ingredient_ref":
                    ref_name = arg[1]
                    if not self.symbol_table.exists(ref_name):
                        self.errors.append(SemanticError(
                            f"Semantic Error: STEP '{step.action}' uses ingredient "
                            f"'{ref_name}', which was never declared"
                        ))
                elif arg[0] == "time_value":
                    _, number, unit = arg
                    if number <= 0:
                        self.errors.append(SemanticError(
                            f"Semantic Error: STEP '{step.action}' has an invalid "
                            f"time value ({number} {unit}) — time must be a "
                            f"positive number"
                        ))