"""
contracts.py - RecipeLang RECIPE CONTRACTS + GOAL-DIRECTED AUTO-TUNER

NOVELTY: RecipeLang programs can state GOALS the finished dish must meet,
and the compiler will PROVE them - or SYNTHESISE the smallest edit that
makes them true.

    RECIPE LightRice
    SERVES 2
    PROTECT lentils                      <- the tuner may not touch this
    ENSURE calories_per_serving <= 300   <- design-by-contract for food
    ENSURE protein_per_serving  >= 12
    ENSURE cook_time            <= 20 minutes

Three compiler ideas are combined:

 1. STATIC VERIFICATION  (like assertions / contracts in Eiffel, Dafny)
    Every ENSURE is checked against the final IR before anything runs.

 2. BLAME ATTRIBUTION    (like explaining a failed proof)
    A violated contract is traced back to the ingredients / steps that
    cause the overshoot, so the cook knows WHY it failed.

 3. PROGRAM SYNTHESIS    (like CEGIS / automatic program repair)
    The compiler searches the space of small edits (change a quantity,
    shorten a cook time, swap an ingredient) with UNIFORM-COST SEARCH.
    The first state that satisfies every contract is therefore the
    CHEAPEST one (least change to the cook's intent). The result is
    re-verified through the REAL pipeline, so the fix is proven, not guessed.
    If no fix exists within the edit limits, the compiler says so and
    reports the closest it could get.

Cost model: changing a quantity / time by x% costs x/100;
swapping an ingredient costs 1.0 (= a 100% change).
"""

import copy
import heapq
import math

from semantic_analyzer import SemanticAnalyzer
from ir_generator import generate_ir
from optimizer import optimize_ir, total_cook_seconds
from knowledge import kcal_of, protein_of, tags_of, ALTS
from repair import forbidden_tags, _rename_arg
from parser import StepNode

METRICS = {
    "calories":             "kcal",
    "calories_per_serving": "kcal",
    "protein":              "g",
    "protein_per_serving":  "g",
    "cook_time":            "min",
}
OPS = {"<=", ">=", "<", ">", "=="}
TIME_TO_MIN = {"second": 1 / 60, "seconds": 1 / 60, "minute": 1, "minutes": 1,
               "hour": 60, "hours": 60}
TO_SECONDS = {"second": 1, "seconds": 1, "minute": 60, "minutes": 60,
              "hour": 3600, "hours": 3600}
EPS = 1e-9
SWAP_COST = 1.0
MAX_STATES = 400_000


# ====================================================================
# 1. MEASURING a recipe (uses the REAL compiler pipeline)
# ====================================================================
def _pipeline(ast):
    a = copy.deepcopy(ast)
    table, errors = SemanticAnalyzer(a).analyze()
    if errors:
        raise ValueError("; ".join(e.message for e in errors))
    ir, _ = optimize_ir(generate_ir(a, table))
    return ir


def measure(ast):
    """Runs the full pipeline and returns the metric dictionary + notes."""
    ir = _pipeline(ast)
    kcal = prot = 0.0
    unknown = set()
    for instr in ir:
        for a in instr.resolved_args:
            if a["kind"] != "ingredient":
                continue
            k = kcal_of(a["name"], a["quantity"], a["unit"])
            p = protein_of(a["name"], a["quantity"], a["unit"])
            if k is None or p is None:
                unknown.add(a["name"])
            kcal += k or 0
            prot += p or 0
    s = ast.serves
    m = {
        "calories": kcal,
        "calories_per_serving": kcal / s if s else None,
        "protein": prot,
        "protein_per_serving": prot / s if s else None,
        "cook_time": total_cook_seconds(ir) / 60,
    }
    return m, sorted(unknown), ir


def _bound(contract):
    """Contract bound expressed in the metric's base unit."""
    if contract.metric == "cook_time":
        return contract.value * TIME_TO_MIN[contract.unit]
    return float(contract.value)


def _holds(value, op, bound):
    if op == "<=": return value <= bound + EPS
    if op == ">=": return value >= bound - EPS
    if op == "<":  return value < bound - EPS
    if op == ">":  return value > bound + EPS
    return abs(value - bound) <= 0.5   # "==" allows rounding of half a unit


def _violation(value, op, bound):
    """How far the value is from satisfying the contract (0 = satisfied)."""
    if _holds(value, op, bound):
        return 0.0
    return abs(value - bound) / max(bound, 1.0) + 1e-6


def verify(ast, metrics=None):
    """Returns a list of rows: (contract, actual, bound, ok, margin)."""
    if metrics is None:
        metrics, _, _ = measure(ast)
    rows = []
    for c in ast.contracts:
        actual, bound = metrics[c.metric], _bound(c)
        ok = _holds(actual, c.op, bound)
        rows.append((c, actual, bound, ok, actual - bound))
    return rows


def fmt_contract(c):
    unit = f" {c.unit}" if c.unit else ""
    return f"{c.metric} {c.op} {c.value}{unit}"


def fmt_val(metric, v):
    return f"{v:.1f} min" if metric == "cook_time" else f"{v:.1f} {METRICS[metric]}"


# ====================================================================
# 2. BLAME ATTRIBUTION - why did the contract fail?
# ====================================================================
def blame(ast, contract, ir):
    """List of (label, amount, share%) that make up the failing metric."""
    parts = {}
    if contract.metric == "cook_time":
        for instr in ir:
            for a in instr.resolved_args:
                if a["kind"] == "time":
                    key = f"step {instr.index}: {instr.action}()"
                    parts[key] = parts.get(key, 0) + a["duration"] * TO_SECONDS[a["unit"]] / 60
    else:
        fn = kcal_of if contract.metric.startswith("calories") else protein_of
        div = ast.serves if contract.metric.endswith("_per_serving") else 1
        for instr in ir:
            for a in instr.resolved_args:
                if a["kind"] == "ingredient":
                    v = fn(a["name"], a["quantity"], a["unit"])
                    if v:
                        parts[a["name"]] = parts.get(a["name"], 0) + v / div
    total = sum(parts.values()) or 1
    return sorted(((k, v, 100 * v / total) for k, v in parts.items()),
                  key=lambda r: -r[1])


# ====================================================================
# 3. THE AUTO-TUNER (uniform-cost search over small edits)
# ====================================================================
class Dim:
    """One thing the tuner may change."""
    def __init__(self, kind, label, base, values=None, **extra):
        self.kind = kind        # "qty" | "time" | "swap"
        self.label = label
        self.base = base        # original value (or 0 for swap)
        self.values = values    # allowed values (qty / time) or option names (swap)
        self.__dict__.update(extra)


def _range(v0, limit):
    lo = max(1, math.ceil(v0 * (1 - limit)))
    hi = max(v0, math.floor(v0 * (1 + limit)))
    return list(range(lo, hi + 1))


def _build_dims(ast, ir, limit):
    forb = forbidden_tags(ast)
    protected = set(ast.protect)
    used = {}
    for instr in ir:
        for a in instr.resolved_args:
            if a["kind"] == "ingredient":
                used[a["name"]] = used.get(a["name"], 0) + 1
    declared = {i.name for i in ast.ingredients}

    dims = []
    for idx, ing in enumerate(ast.ingredients):
        if ing.name in protected or ing.name not in used:
            continue
        # option 0 = keep the ingredient, others = unit-compatible swaps
        options = [ing.name]
        for alt in ALTS.get(ing.name, []):
            if alt in declared or tags_of(alt) & forb:
                continue
            if kcal_of(alt, 1, ing.unit) is None or protein_of(alt, 1, ing.unit) is None:
                continue
            options.append(alt)
        dims.append(Dim("qty", f"{ing.name} quantity", ing.quantity,
                        _range(ing.quantity, limit), ing_index=idx, uses=used[ing.name],
                        unit=ing.unit, name=ing.name))
        if len(options) > 1:
            dims.append(Dim("swap", f"{ing.name} swap", 0, options, ing_index=idx,
                            uses=used[ing.name], unit=ing.unit, name=ing.name))

    # time literals in top-level STEP / CALL arguments
    for si, node in enumerate(ast.steps):
        for ai, arg in enumerate(node.args):
            if arg[0] != "time_value":
                continue
            _, v0, unit = arg
            probe = copy.deepcopy(ast)
            probe.steps[si].args[ai] = ("time_value", v0 + 1, unit)
            sec_per_unit = (measure(probe)[0]["cook_time"] - measure(ast)[0]["cook_time"]) * 60
            if sec_per_unit <= 0:
                continue
            what = node.action if isinstance(node, StepNode) else f"call {node.name}"
            dims.append(Dim("time", f"{what}() time ({unit})", v0, _range(v0, limit),
                            step_index=si, arg_index=ai, unit=unit, sec=sec_per_unit))
    return dims, used


def _state_metrics(ast, dims, state, base_cook_min, used):
    kcal = prot = 0.0
    cook = base_cook_min
    qty = {}
    swap = {}
    for d, v in zip(dims, state):
        if d.kind == "qty":
            qty[d.ing_index] = d.values[v]
        elif d.kind == "swap":
            swap[d.ing_index] = d.values[v]
        else:
            cook += (d.values[v] - d.base) * d.sec / 60
    # EVERY ingredient counts (protected / untouched ones are constants)
    for i, ing in enumerate(ast.ingredients):
        uses = used.get(ing.name, 0)
        q = qty.get(i, ing.quantity)
        nm = swap.get(i, ing.name)
        kcal += uses * (kcal_of(nm, q, ing.unit) or 0)
        prot += uses * (protein_of(nm, q, ing.unit) or 0)
    s = ast.serves
    return {"calories": kcal, "calories_per_serving": kcal / s if s else None,
            "protein": prot, "protein_per_serving": prot / s if s else None,
            "cook_time": cook}


def _cost(dims, state):
    total = 0.0
    for d, v in zip(dims, state):
        if d.kind == "swap":
            total += SWAP_COST if v != 0 else 0
        else:
            total += abs(d.values[v] - d.base) / d.base
    return total


def _neighbours(dims, state):
    """Moves go only OUTWARD from the original value, so every step costs >= 0."""
    for i, (d, v) in enumerate(zip(dims, state)):
        if d.kind == "swap":
            if v == 0:
                for o in range(1, len(d.values)):
                    yield state[:i] + (o,) + state[i + 1:]
            continue
        b = d.values.index(d.base)
        if v >= b and v + 1 < len(d.values):
            yield state[:i] + (v + 1,) + state[i + 1:]
        if v <= b and v - 1 >= 0:
            yield state[:i] + (v - 1,) + state[i + 1:]


def tune(ast, limit=0.5):
    """
    Search for the cheapest edit that satisfies every contract.
    Returns a dict with: status ("ok" | "already" | "infeasible" | "budget"),
    new_ast, edits, cost, explored, closest (for the failure cases).
    """
    base_metrics, unknown, ir = measure(ast)
    rows = verify(ast, base_metrics)
    if all(r[3] for r in rows):
        return {"status": "already", "explored": 0}

    dims, used = _build_dims(ast, ir, limit)
    if not dims:
        return {"status": "infeasible", "explored": 0, "closest": None, "dims": dims,
                "reason": "nothing can be changed (every ingredient is PROTECTed or unused)"}

    start = tuple(d.values.index(d.base) if d.kind != "swap" else 0 for d in dims)
    base_cook = base_metrics["cook_time"]

    def score(state):
        m = _state_metrics(ast, dims, state, base_cook, used)
        total = 0.0
        for c in ast.contracts:
            total += _violation(m[c.metric], c.op, _bound(c))
        return total, m

    # self-check: the fast model must agree with the real pipeline at the start state
    m0 = _state_metrics(ast, dims, start, base_cook, used)
    for key in ("calories", "protein", "cook_time"):
        assert abs(m0[key] - base_metrics[key]) < 1e-6, f"model mismatch on {key}"

    heap = [(0.0, 0, start)]
    seen = {start}
    counter = 1
    explored = 0
    closest = (score(start)[0], 0.0, start)
    while heap:
        cost, _, state = heapq.heappop(heap)
        explored += 1
        viol, _m = score(state)
        if viol == 0:
            return {"status": "ok", "dims": dims, "state": state, "cost": cost,
                    "explored": explored, "new_ast": _apply(ast, dims, state),
                    "metrics_model": _m}
        if viol < closest[0]:
            closest = (viol, cost, state)
        if explored >= MAX_STATES:
            return {"status": "budget", "dims": dims, "explored": explored,
                    "closest": closest}
        for nxt in _neighbours(dims, state):
            if nxt in seen:
                continue
            seen.add(nxt)
            heapq.heappush(heap, (_cost(dims, nxt), counter, nxt))
            counter += 1
    return {"status": "infeasible", "dims": dims, "explored": explored, "closest": closest,
            "space": len(seen)}


def _apply(ast, dims, state):
    """Builds the tuned AST from a search state."""
    new = copy.deepcopy(ast)
    mapping = {}
    for d, v in zip(dims, state):
        if d.kind == "qty":
            new.ingredients[d.ing_index].quantity = d.values[v]
        elif d.kind == "swap" and v != 0:
            mapping[d.name] = d.values[v]
        elif d.kind == "time":
            _, _, unit = new.steps[d.step_index].args[d.arg_index]
            new.steps[d.step_index].args[d.arg_index] = ("time_value", d.values[v], unit)
    if mapping:
        for ing in new.ingredients:
            if ing.name in mapping:
                ing.name = mapping[ing.name]
        for node in new.steps:
            node.args = [_rename_arg(a, mapping) for a in node.args]
        for p in new.procedures:
            for node in p.body:
                node.args = [_rename_arg(a, mapping) for a in node.args]
    return new


def describe_edits(dims, state):
    """Human-readable list of the changes in a state."""
    out = []
    for d, v in zip(dims, state):
        if d.kind == "swap":
            if v != 0:
                out.append(f"swap '{d.name}' for '{d.values[v]}'")
        else:
            new = d.values[v]
            if new != d.base:
                pct = round(100 * (new - d.base) / d.base)
                if d.kind == "qty":
                    unit = f" {d.unit}" if d.unit else ""
                    out.append(f"{d.name}: {d.base}{unit} -> {new}{unit} ({pct:+d}%)")
                else:
                    out.append(f"{d.label}: {d.base} -> {new} ({pct:+d}%)")
    return out


# ====================================================================
# 4. Pretty report used by demo.py and the CLI
# ====================================================================
def print_verification(ast, rows, indent="  "):
    print(f"{indent}{'Contract':<36} {'Actual':<14} {'Verdict'}")
    print(f"{indent}{'-'*36} {'-'*14} {'-'*22}")
    for c, actual, bound, ok, margin in rows:
        verdict = "PASS" if ok else f"FAIL (off by {abs(margin):.1f})"
        print(f"{indent}{fmt_contract(c):<36} {fmt_val(c.metric, actual):<14} {verdict}")


def report(ast, limit=0.5, write_path=None, out=print):
    """Full contract workflow. Returns the (possibly tuned) AST, or None on failure."""
    from repair import unparse
    metrics, unknown, ir = measure(ast)
    rows = verify(ast, metrics)
    print_verification(ast, rows)
    if unknown:
        out(f"\n  note: no nutrition data for {', '.join(unknown)} (counted as 0)")
    failed = [r for r in rows if not r[3]]
    if not failed:
        out("\n  RESULT: every contract is PROVEN for this recipe.")
        return ast

    out("\n  BLAME ATTRIBUTION - what makes each failing contract fail:")
    for c, actual, bound, ok, margin in failed:
        out(f"    {fmt_contract(c)}   (actual {fmt_val(c.metric, actual)})")
        for label, amount, share in blame(ast, c, ir)[:4]:
            bar = "#" * max(1, round(share / 5))
            out(f"      {label:<22} {amount:8.1f}  {share:5.1f}%  {bar}")

    out(f"\n  AUTO-TUNER: searching for the cheapest edit (each value may move +/-{round(limit*100)}%)")
    if ast.protect:
        out(f"  PROTECTED (never changed): {', '.join(ast.protect)}")
    res = tune(ast, limit)
    if res["status"] == "ok":
        edits = describe_edits(res["dims"], res["state"])
        out(f"  Explored {res['explored']} candidate recipes in cost order -> "
            f"the first valid one is the CHEAPEST (total change cost {res['cost']:.2f}).")
        out("\n  SYNTHESISED FIX:")
        for e in edits:
            out(f"    - {e}")
        new = res["new_ast"]
        m2, _, _ = measure(new)
        rows2 = verify(new, m2)
        out("\n  RE-VERIFICATION through the real compiler pipeline:")
        print_verification(new, rows2)
        if not all(r[3] for r in rows2):
            out("  !! internal error: tuned recipe failed re-verification")
            return None
        out("\n  RESULT: all contracts now PROVEN. Tuned program:\n")
        src = unparse(new)
        for i, line in enumerate(src.splitlines(), 1):
            out(f"    {i:>2} | {line}")
        if write_path:
            with open(write_path, "w", encoding="utf-8") as f:
                f.write(src)
            out(f"\n  Saved to: {write_path}")
        return new
    if res["status"] == "infeasible":
        out(f"  Explored all {res['explored']} reachable recipes: NO combination of allowed edits "
            f"satisfies every contract."
            if res["explored"] else f"  {res.get('reason')}")
        if res.get("closest") and res["closest"][2] is not None:
            viol, cost, state = res["closest"]
            edits = describe_edits(res["dims"], state) or ["(no edits)"]
            out("  Closest the tuner could get:")
            for e in edits:
                out(f"    - {e}")
        out("\n  RESULT: contracts are IMPOSSIBLE within these limits. "
            "Relax a goal, PROTECT fewer ingredients, or allow bigger edits (--limit 80).")
        return None
    out(f"  Stopped after {res['explored']} candidates (search budget). Try a looser goal.")
    return None


if __name__ == "__main__":
    import sys
    from parser import parse_source
    args = sys.argv[1:]
    lim = 0.5
    if "--limit" in args:
        lim = int(args[args.index("--limit") + 1]) / 100
    files = [a for i, a in enumerate(args)
             if not a.startswith("--") and not (i > 0 and args[i - 1] == "--limit")]
    path = files[0]
    tree = parse_source(open(path).read())
    table, errs = SemanticAnalyzer(tree).analyze()
    if errs:
        for e in errs:
            print(" -", e)
        sys.exit(1)
    print(f"\nRecipe contracts for {tree.name}\n")
    report(tree, lim, write_path=path.rsplit(".", 1)[0] + "_tuned.recipe" if "--write" in args else None)
