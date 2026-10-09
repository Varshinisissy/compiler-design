"""
interpreter.py — RecipeLang Phase 2 Interpreter / Execution Engine

Satisfies the manual's "Interpreter or Execution Engine: expression
evaluation, program execution, runtime environment, and variable
management" item.

Walks the IR produced by ir_generator.py and EXECUTES it in order:
  - "Expression evaluation" here means resolving each step's
    arguments to concrete values (already done in the IR — this
    module consumes those resolved values).
  - "Program execution" = running through every IR instruction in
    sequence and producing an execution log.
  - "Runtime environment" / "variable management" = the
    RuntimeEnvironment class below, which tracks how much of each
    ingredient has actually been used as execution proceeds — this
    is RecipeLang's equivalent of tracking variable state at runtime.
"""

from ir_generator import IRInstruction


class RuntimeEnvironment:
    """Tracks ingredient usage while the IR executes — the RecipeLang
    equivalent of a runtime variable/memory environment in a
    general-purpose language's interpreter."""

    def __init__(self):
        self.used_ingredients = {}   # name -> {"quantity": int, "unit": str|None}

    def record_use(self, name, quantity, unit):
        if name not in self.used_ingredients:
            self.used_ingredients[name] = {"quantity": 0, "unit": unit}
        self.used_ingredients[name]["quantity"] += quantity


def execute(ir: list[IRInstruction]):
    """Runs the IR instructions in order. Returns (environment, log)
    where `log` is a list of human-readable execution lines and
    `environment` is the final RuntimeEnvironment state."""
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
            else:  # time
                parts.append(f"{arg['duration']} {arg['unit']}")

        log.append(f"  Executing Step {instr.index}: {instr.action}({', '.join(parts)}) -> done")

    return env, log
