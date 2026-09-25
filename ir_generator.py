"""
ir_generator.py — RecipeLang Phase 2 Intermediate Representation
"""

from parser import RecipeNode
from semantic_analyzer import SymbolTable


class IRInstruction:
    def __init__(self, index, action, resolved_args):
        self.index = index
        self.action = action
        self.resolved_args = resolved_args

    def __repr__(self):
        return f"IR[{self.index}] {self.action}({self.resolved_args})"


def generate_ir(recipe: RecipeNode, symbol_table: SymbolTable):
    ir = []
    for i, step in enumerate(recipe.steps, start=1):
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
        ir.append(IRInstruction(i, step.action, resolved_args))
    return ir


def format_ir_line(instr: IRInstruction) -> str:
    if not instr.resolved_args:
        return f"  [{instr.index}] {instr.action}()"

    parts = []
    for arg in instr.resolved_args:
        if arg["kind"] == "ingredient":
            unit_str = f" {arg['unit']}" if arg["unit"] else ""
            parts.append(f"{arg['name']}={arg['quantity']}{unit_str}")
        else:
            parts.append(f"{arg['duration']} {arg['unit']}")
    return f"  [{instr.index}] {instr.action}({', '.join(parts)})"