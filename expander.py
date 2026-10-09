"""
expander.py - RecipeLang PROCEDURE EXPANSION (inlining)

RecipeLang supports user-defined procedures:

    DEFINE tempering(spice)
      STEP add(spice)
      STEP stir()
    END
    ...
    CALL tempering(cumin)

At compile time every CALL is replaced by the procedure's body, with each
parameter substituted by the actual argument. This is the compiler
optimization / lowering technique called INLINING (macro expansion).
Everything after this pass (semantic checks, IR, interpreter) sees only
plain steps, so the rest of the pipeline did not need to change.

This pass also reports procedure errors:
  - duplicate procedure names / duplicate parameter names
  - CALL to an undefined procedure
  - wrong number of arguments (arity mismatch)
  - recursive procedures (found by searching the call graph for cycles)
  - names used inside a procedure that are neither parameters nor ingredients
"""

from parser import StepNode, CallNode


def _subst(arg, bindings):
    """Replace a parameter reference with the actual argument bound to it."""
    if arg[0] == "ingredient_ref" and arg[1] in bindings:
        return bindings[arg[1]]
    return arg


def _fmt_arg(a):
    return a[1] if a[0] == "ingredient_ref" else f"{a[1]} {a[2]}"


def describe_call(node):
    return f"CALL {node.name}({', '.join(_fmt_arg(a) for a in node.args)})"


def describe_step(node):
    rep = f"REPEAT {node.repeat} " if node.repeat != 1 else ""
    return f"{rep}STEP {node.action}({', '.join(_fmt_arg(a) for a in node.args)})"


def _reaches(procs, start, target, seen=None):
    """True if procedure `start` can (directly or indirectly) call `target`."""
    seen = seen if seen is not None else set()
    for node in procs[start].body:
        if isinstance(node, CallNode) and node.name in procs:
            if node.name == target:
                return True
            if node.name not in seen:
                seen.add(node.name)
                if _reaches(procs, node.name, target, seen):
                    return True
    return False


def expand(recipe):
    """Returns (flat_steps, errors, log).
    log is a list of (call_node, [expanded StepNodes]) for top-level calls."""
    errors, log = [], []

    def err(msg):
        if msg not in errors:
            errors.append(msg)

    declared = {i.name for i in recipe.ingredients}
    procs = {}
    for p in recipe.procedures:
        if p.name in procs:
            err(f"procedure '{p.name}' is defined more than once")
            continue
        procs[p.name] = p
        if len(set(p.params)) != len(p.params):
            err(f"procedure '{p.name}' has a duplicate parameter name")

    cyclic = {n for n in procs if _reaches(procs, n, n)}
    for n in sorted(cyclic):
        err(f"procedure '{n}' calls itself (directly or indirectly) - "
            f"recursion is not allowed")

    expanded_procs = set()

    def walk(nodes, bindings, out, top, origin):
        for node in nodes:
            args = [_subst(a, bindings) for a in node.args]
            if isinstance(node, StepNode):
                step = StepNode(node.action, args, node.repeat)
                step.origin = origin
                out.append(step)
                continue
            proc = procs.get(node.name)
            if proc is None:
                err(f"CALL to undefined procedure '{node.name}'")
                continue
            if node.name in cyclic:
                continue
            if len(args) != len(proc.params):
                err(f"procedure '{proc.name}' expects {len(proc.params)} "
                    f"argument(s) but CALL gives {len(args)}")
                continue
            expanded_procs.add(proc.name)
            for _ in range(node.repeat):
                start = len(out)
                walk(proc.body, dict(zip(proc.params, args)), out, False, proc.name)
                if top:
                    log.append((CallNode(node.name, args, 1), out[start:]))

    steps = []
    walk(recipe.steps, {}, steps, True, None)

    # procedures that were never expanded still get their bodies checked
    for p in procs.values():
        if p.name in expanded_procs or p.name in cyclic:
            continue
        known = set(p.params) | declared
        for node in p.body:
            for a in node.args:
                if a[0] == "ingredient_ref" and a[1] not in known:
                    err(f"procedure '{p.name}' uses '{a[1]}', which is neither "
                        f"a parameter nor a declared ingredient")
    return steps, errors, log
