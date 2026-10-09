"""
ir_generator.py — RecipeLang Phase 2 Intermediate Representation

Satisfies the manual's "Intermediate Code: three-address code,
quadruples, triples, or other intermediate representations" item.

RecipeLang's IR is a flat list of IRInstruction objects: one per
STEP, with every ingredient reference RESOLVED against the symbol
table (name -> actual quantity + unit), instead of just a bare name.
This is the same core idea as three-address code resolving a variable
name to its stored value/address — the IR no longer depends on the
original source text or the symbol table to be understood; it is
fully self-contained, which is the defining property of an IR.

Precondition: only call generate_ir() AFTER semantic analysis has
passed with zero errors — this function assumes every ingredient
reference is valid and every quantity/time value is positive.
"""

from parser import RecipeNode
from semantic_analyzer import SymbolTable


class IRInstruction:
    """One resolved step: an action plus its fully-resolved argument list."""
    def __init__(self, index, action, resolved_args):
        self.index = index                # position in the recipe (1-based)
        self.action = action              # e.g. "add", "cook", "serve"
        self.resolved_args = resolved_args  # list of dicts, see generate_ir()

    def __repr__(self):
        return f"IR[{self.index}] {self.action}({self.resolved_args})"


def generate_ir(recipe: RecipeNode, symbol_table: SymbolTable):
    """Builds the flat IR list from a semantically-validated AST."""
    ir = []
    index = 1
    for step in getattr(recipe, "expanded_steps", recipe.steps):
        resolved_args = []
        for arg in step.args:
            if arg[0] == "ingredient_ref":
                entry = symbol_table.lookup(arg[1])
                resolved_args.append({
                    "kind": "ingredient",
                    "name": entry.name,
                    "quantity": entry.quantity,
                    "unit": entry.unit,
                })
            elif arg[0] == "time_value":
                _, number, unit = arg
                resolved_args.append({
                    "kind": "time",
                    "duration": number,
                    "unit": unit,
                })
        # REPEAT n is "unrolled": the step becomes n separate IR instructions
        for _ in range(step.repeat):
            ir.append(IRInstruction(index, step.action, [dict(a) for a in resolved_args]))
            index += 1
    return ir


def format_ir_line(instr: IRInstruction) -> str:
    """Formats one IR instruction as a single readable line for printing."""
    if not instr.resolved_args:
        return f"  [{instr.index}] {instr.action}()"

    parts = []
    for arg in instr.resolved_args:
        if arg["kind"] == "ingredient":
            unit_str = f" {arg['unit']}" if arg["unit"] else ""
            parts.append(f"{arg['name']}={arg['quantity']}{unit_str}")
        else:  # time
            parts.append(f"{arg['duration']} {arg['unit']}")
    return f"  [{instr.index}] {instr.action}({', '.join(parts)})"
