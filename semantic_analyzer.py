"""
semantic_analyzer.py — RecipeLang Phase 2 Semantic Analyzer + Symbol Table

Takes the AST built by parser.py (a RecipeNode) and performs the
semantic checks defined in Section 13 of the design document:

  1. Ingredient must be declared before use in a STEP.
  2. No duplicate ingredient declarations within a recipe.
  3. An ingredient's quantity must be a positive number.
  4. A STEP's time value (e.g. "10 minutes") must be a positive number.

Design decision: unlike the lexer and parser (which stop at the FIRST
error they hit), this analyzer collects ALL semantic errors before
reporting. Semantic checks are independent of each other — finding a
duplicate ingredient doesn't prevent also checking whether a STEP
references an undeclared one — so collecting everything gives the
student one full error report per run instead of a frustrating
one-error-at-a-time loop. This mirrors how real compilers usually
report semantic diagnostics (think: a Java or C compiler listing
several errors in one compile).
"""

from parser import RecipeNode
from expander import expand
from knowledge import KB, DIETS, ALLERGENS, tags_of


class SemanticError:
    """One semantic diagnostic message."""
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return self.message


class SymbolTableEntry:
    """One row of the symbol table: everything known about one
    declared ingredient."""
    def __init__(self, name, type_, quantity, unit, scope):
        self.name = name
        self.type = type_
        self.quantity = quantity
        self.unit = unit
        self.scope = scope


class SymbolTable:
    """A simple name -> SymbolTableEntry map. RecipeLang v1 has only
    one scope (the single RECIPE block), so this is intentionally not
    a stack of nested scopes — just one flat table per recipe."""

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
    """Walks a validated AST (RecipeNode) and performs semantic
    analysis, building the symbol table along the way."""

    def __init__(self, recipe: RecipeNode):
        self.recipe = recipe
        self.symbol_table = SymbolTable()
        self.errors = []

    def analyze(self):
        """Runs all semantic checks in order. Returns (symbol_table, errors).
        `errors` is empty if the recipe is fully semantically valid."""
        self._check_ingredients()
        steps, expand_errors, log = expand(self.recipe)
        self.recipe.expanded_steps = steps       # flat steps (CALLs inlined)
        self.recipe.expansion_log = log
        for msg in expand_errors:
            self.errors.append(SemanticError(f"Semantic Error: {msg}"))
        self._check_steps()
        self._check_extensions()
        self._check_constraints()
        self._check_contracts()
        # the same mistake can appear once per expanded CALL: report it only once
        unique, seen = [], set()
        for e in self.errors:
            if e.message not in seen:
                seen.add(e.message)
                unique.append(e)
        self.errors = unique
        return self.symbol_table, self.errors

    # --- Rule 2 (no duplicates) + Rule 3 (valid quantity) ---------------
    def _check_ingredients(self):
        for ing in self.recipe.ingredients:
            if self.symbol_table.exists(ing.name):
                self.errors.append(SemanticError(
                    f"Semantic Error: ingredient '{ing.name}' is declared more than "
                    f"once in recipe '{self.recipe.name}'"
                ))
                # Keep the FIRST declaration in the table; don't overwrite it
                # with the duplicate, and don't re-check its quantity again.
                continue

            if ing.quantity <= 0:
                self.errors.append(SemanticError(
                    f"Semantic Error: ingredient '{ing.name}' has an invalid "
                    f"quantity ({ing.quantity}) — quantity must be a positive number"
                ))
                # Still declare it (with the invalid quantity) so that any
                # STEP referencing it doesn't ALSO wrongly report
                # "undeclared ingredient" on top of this error.

            self.symbol_table.declare(
                ing.name, "INGREDIENT", ing.quantity, ing.unit, self.recipe.name
            )

    # --- Rule 1 (declared-before-use) + Rule 4 (valid time value) -------
    def _check_steps(self):
        for step in self.recipe.expanded_steps:
            where = f" (inside procedure '{step.origin}')" if step.origin else ""
            for arg in step.args:
                if arg[0] == "ingredient_ref":
                    ref_name = arg[1]
                    if not self.symbol_table.exists(ref_name):
                        self.errors.append(SemanticError(
                            f"Semantic Error: STEP '{step.action}' uses ingredient "
                            f"'{ref_name}', which was never declared{where}"
                        ))
                elif arg[0] == "time_value":
                    _, number, unit = arg
                    if number <= 0:
                        self.errors.append(SemanticError(
                            f"Semantic Error: STEP '{step.action}' has an invalid "
                            f"time value ({number} {unit}) — time must be a "
                            f"positive number{where}"
                        ))

    # --- Rules 5 and 6: SERVES and REPEAT must be positive ---------------
    def _check_extensions(self):
        if self.recipe.serves is not None and self.recipe.serves <= 0:
            self.errors.append(SemanticError(
                f"Semantic Error: SERVES has an invalid value ({self.recipe.serves}) "
                f"— servings must be a positive number"
            ))
        for step in self.recipe.steps:
            if step.repeat <= 0:
                self.errors.append(SemanticError(
                    f"Semantic Error: REPEAT before '{getattr(step, 'action', getattr(step, 'name', '?'))}' has an "
                    f"invalid count ({step.repeat}) — it must be a positive number"
                ))

    # --- Rules 7 and 8: DIET and AVOID constraints --------------------------
    def _check_constraints(self):
        recipe = self.recipe
        forbidden = {}   # tag -> reason text
        if recipe.diet is not None:
            if recipe.diet not in DIETS:
                self.errors.append(SemanticError(
                    f"Semantic Error: unknown DIET '{recipe.diet}' "
                    f"(allowed: {', '.join(sorted(DIETS))})"))
            else:
                for tag in DIETS[recipe.diet]:
                    forbidden[tag] = f"DIET {recipe.diet}"
        for allergen in recipe.avoid:
            if allergen not in ALLERGENS:
                self.errors.append(SemanticError(
                    f"Semantic Error: unknown AVOID '{allergen}' "
                    f"(allowed: {', '.join(sorted(ALLERGENS))})"))
            else:
                forbidden[allergen] = f"AVOID {allergen}"
        if not forbidden:
            return
        for ing in recipe.ingredients:
            for tag in sorted(tags_of(ing.name)):
                if tag in forbidden:
                    sub = KB[ing.name]["sub"]
                    hint = f" - try replacing it with '{sub}'" if sub else ""
                    self.errors.append(SemanticError(
                        f"Semantic Error: ingredient '{ing.name}' is tagged '{tag}', "
                        f"which violates {forbidden[tag]}{hint}"))

    # --- Rules 9 and 10: ENSURE contracts and PROTECT declarations ----------
    def _check_contracts(self):
        from contracts import METRICS, OPS, TIME_TO_MIN
        recipe = self.recipe
        for c in recipe.contracts:
            where = f"ENSURE {c.metric} (line {c.line})"
            if c.metric not in METRICS:
                self.errors.append(SemanticError(
                    f"Semantic Error: {where}: unknown metric "
                    f"(allowed: {', '.join(sorted(METRICS))})"))
                continue
            if c.op not in OPS:
                self.errors.append(SemanticError(
                    f"Semantic Error: {where}: unknown operator '{c.op}'"))
            if c.metric.endswith("_per_serving") and recipe.serves is None:
                self.errors.append(SemanticError(
                    f"Semantic Error: {where}: needs a SERVES line to compute per-serving values"))
            if c.metric == "cook_time" and c.unit not in TIME_TO_MIN:
                self.errors.append(SemanticError(
                    f"Semantic Error: {where}: cook_time needs a time unit, e.g. 20 minutes"))
            if c.metric != "cook_time" and c.unit in TIME_TO_MIN:
                self.errors.append(SemanticError(
                    f"Semantic Error: {where}: a time unit only makes sense for cook_time"))
            if c.value <= 0:
                self.errors.append(SemanticError(
                    f"Semantic Error: {where}: the target value must be positive"))
        for name in recipe.protect:
            if not self.symbol_table.exists(name):
                self.errors.append(SemanticError(
                    f"Semantic Error: PROTECT '{name}' refers to an ingredient that was never declared"))
