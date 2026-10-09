"""
analysis.py - RecipeLang KITCHEN DATA-FLOW ANALYSIS

The ordinary semantic analyzer checks each statement on its own
(declared? positive?). This pass is different: it is FLOW-SENSITIVE.
It "walks" the IR in order, carrying an abstract kitchen state along
(pan hot or cold, what is in the pan, cooked yet, served yet) and
checks that the ORDER of the steps makes sense.

This is the same idea as data-flow / state analysis in real compilers
(e.g. "variable used before it is assigned", "file used after close").

State carried along the program:
    pan_hot  : has heat_pan()/boil() happened?
    contents : which ingredients are in the pan
    cooked   : has cook() happened?
    served   : has serve() happened?
"""

HEATERS = {"heat_pan", "boil"}


def analyze_flow(ir):
    """Returns (errors, warnings, trace). trace has one line per instruction."""
    errors, warnings, trace = [], [], []
    pan_hot = False
    contents = []
    cooked = False
    served = False

    for instr in ir:
        n, act = instr.index, instr.action
        names = [a["name"] for a in instr.resolved_args if a["kind"] == "ingredient"]

        if served and act != "serve":
            errors.append(f"step {n}: {act}() happens after serve() - the dish is already served")

        if act in HEATERS:
            pan_hot = True
            for nm in names:
                if nm not in contents:
                    contents.append(nm)
        elif act == "add":
            if not pan_hot:
                warnings.append(f"step {n}: adding {', '.join(names)} to a cold pan "
                                f"(no heat_pan() before it)")
            for nm in names:
                if nm not in contents:
                    contents.append(nm)
        elif act == "stir":
            if not contents:
                warnings.append(f"step {n}: stir() on an empty pan")
        elif act == "cook":
            if not contents:
                errors.append(f"step {n}: cook() with nothing in the pan")
            if not pan_hot:
                errors.append(f"step {n}: cook() on a cold pan (heat it first)")
            cooked = True
        elif act == "serve":
            if not cooked:
                errors.append(f"step {n}: serve() before the food was cooked")
            served = True

        state = (f"pan={'HOT ' if pan_hot else 'COLD'}  "
                 f"contents={{{', '.join(contents)}}}  "
                 f"cooked={'yes' if cooked else 'no'}")
        trace.append((n, act, state))

    return errors, warnings, trace
