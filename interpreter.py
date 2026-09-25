"""
interpreter.py — RecipeLang Phase 2 Interpreter / Execution Engine
"""

from ir_generator import IRInstruction


class RuntimeEnvironment:
    def __init__(self):
        self.used_ingredients = {}

    def record_use(self, name, quantity, unit):
        if name not in self.used_ingredients:
            self.used_ingredients[name] = {"quantity": 0, "unit": unit}
        self.used_ingredients[name]["quantity"] += quantity


def execute(ir):
    env = RuntimeEnvironment()
    log = []

    for instr in ir:
        if not instr.resolved_args:
            log.append(f"  Executing Step {instr.index}: {instr.action}() -> done")
            continue

        parts = []
        for arg in instr.resolved_args:
            if arg["kind"] == "ingredient":
                unit_str = f" {arg['unit']}" if arg["unit"] else ""
                parts.append(f"{arg['name']} ({arg['quantity']}{unit_str})")
                env.record_use(arg["name"], arg["quantity"], arg["unit"])
            else:
                parts.append(f"{arg['duration']} {arg['unit']}")

        log.append(f"  Executing Step {instr.index}: {instr.action}({', '.join(parts)}) -> done")

    return env, log