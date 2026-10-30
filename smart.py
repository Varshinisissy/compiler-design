"""
smart.py - RecipeLang SMART COMPILER

An ordinary compiler translates the program it is given and stops at the
first mistake.  The SMART compiler goes beyond that.  It uses five extra
techniques, each one a separate section of this file:

  1. AUTO ERROR DETECTION & FIXING   (self-healing, 3 levels)
       level 1  source text : illegal characters, misspelt keywords, missing
                              '()' or '=' are repaired, then the program is re-parsed
       level 2  meaning     : undeclared / duplicate ingredients, zero or
                              negative numbers, bad CALLs, diet violations
       level 3  kitchen flow: cold pan, empty pan, serving too early, no serve()
     Every fix is applied, then the WHOLE program is re-checked (fix-point
     loop), so a fix that causes a new error is caught and fixed as well.

  2. REASONING          a forward-chaining inference engine. Facts about the
                        recipe (ingredients, actions, tags, numbers) are fed to
                        IF-THEN rules; new facts are derived and every
                        conclusion keeps its "because" chain. Some conclusions
                        trigger decisions (e.g. rice cooked too briefly ->
                        the cooking time is raised).

  3. LEARNING           the compiler keeps a persistent memory
                        (smart_memory.json). It learns typical quantities,
                        typical cooking times and which ingredients go
                        together from every recipe it compiles, and uses that
                        to fill gaps, flag outliers and make suggestions.

  4. ADAPTIVE OPTIMISATION   optimisation passes are scheduled by how much each
                        pass has paid off in the past (learned profit).

  5. ADAPTIVE STRATEGY CHOICE   when several ways of fixing an error exist, the
                        compiler ranks them by their learned success rate, so
                        its behaviour changes as it gains experience.

Run:   python smart.py recipe.recipe
       python smart.py recipe.recipe --no-learn      (do not update memory)
       python smart.py --train corpus                (learn from a folder)
"""

import os
import re
import sys
import copy
import json
import math
import glob
import difflib
import statistics

from lexer import KEYWORDS, LexicalError
from parser import parse_source, SyntaxErrorRL, StepNode, CallNode, IngredientNode
from semantic_analyzer import SemanticAnalyzer
from ir_generator import generate_ir
from analysis import analyze_flow, HEATERS
from expander import _reaches
from repair import try_repair, unparse
from knowledge import KB, tags_of
import contracts

HERE = os.path.dirname(os.path.abspath(__file__))
MEMORY_PATH = os.path.join(HERE, "smart_memory.json")
CORPUS_DIR = os.path.join(HERE, "corpus")

KNOWN_ACTIONS = ["heat_pan", "add", "stir", "cook", "serve", "boil"]
# minimum sensible cooking minutes per ingredient (domain knowledge for reasoning)
MIN_COOK = {"rice": 10, "lentils": 15, "potato": 15, "chicken": 15,
            "pasta": 8, "egg": 6, "fish": 8}


# =====================================================================
# 3. LEARNING - persistent memory
# =====================================================================
class Memory:
    def __init__(self, path=MEMORY_PATH):
        self.path = path
        self.data = {"recipes": {}, "strategy": {}, "pass_gain": {}, "runs": 0}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.data.update(json.load(f))
            except (OSError, ValueError):
                pass

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=1, sort_keys=True)

    @property
    def recipes(self):
        return self.data["recipes"]

    # ---- learning from a recipe ------------------------------------------
    def learn_recipe(self, ast, cook_min):
        self.recipes[ast.name] = {
            "ing": {i.name: [i.quantity, i.unit] for i in ast.ingredients},
            "cook": round(cook_min, 2),
            "serves": ast.serves,
        }

    # ---- what has been learned --------------------------------------------
    def typical_qty(self, name, unit):
        vals = [r["ing"][name][0] for r in self.recipes.values()
                if name in r["ing"] and r["ing"][name][1] == unit]
        return int(round(statistics.median(vals))) if vals else None

    def neighbours(self, names, exclude=None, k=5, min_sim=0.25):
        """Most similar remembered recipes (Jaccard similarity of ingredient sets)."""
        a = set(names)
        scored = []
        for rname, r in self.recipes.items():
            if rname == exclude:
                continue
            b = set(r["ing"])
            sim = len(a & b) / len(a | b) if a | b else 0
            if sim >= min_sim:
                scored.append((sim, rname, r["cook"]))
        scored.sort(key=lambda t: (-t[0], t[1]))
        return scored[:k]

    def expected_cook(self, names, exclude=None):
        """(expected minutes, tolerance, n_neighbours) or None.
        ADAPTIVE: the tolerance shrinks as more similar recipes are known."""
        nb = self.neighbours(names, exclude)
        if not nb:
            return None
        exp = statistics.median([c for _, _, c in nb])
        tol = max(3.0, exp * 0.9 / math.sqrt(len(nb)))
        return exp, tol, len(nb)

    def associations(self, names, exclude=None, min_support=3, min_conf=0.7):
        """Ingredients that usually accompany the given ones but are missing."""
        names = set(names)
        pool = [set(r["ing"]) for n, r in self.recipes.items() if n != exclude]
        best = {}
        for x in names:
            with_x = [s for s in pool if x in s]
            if len(with_x) < min_support:
                continue
            for y in {y for s in with_x for y in s} - names:
                sup = sum(1 for s in with_x if y in s)
                conf = sup / len(with_x)
                if sup >= min_support and conf >= min_conf and conf > best.get(y, (0,))[0]:
                    best[y] = (conf, sup, x, len(with_x))
        return sorted(((y, *v) for y, v in best.items()), key=lambda t: (-t[1], t[0]))

    # ---- adaptive strategy statistics -----------------------------------------
    def rank(self, kind, options):
        """Order fix strategies by learned success rate (ties keep the default order)."""
        stats = self.data["strategy"].get(kind, {})
        def score(o):
            ok, tries = stats.get(o, [0, 0])
            return (ok + 1) / (tries + 2)
        return sorted(options, key=lambda o: -score(o))

    def rate(self, kind, option):
        ok, tries = self.data["strategy"].get(kind, {}).get(option, [0, 0])
        return ok, tries

    def record(self, kind, option, ok):
        s = self.data["strategy"].setdefault(kind, {}).setdefault(option, [0, 0])
        s[1] += 1
        s[0] += 1 if ok else 0

    # ---- adaptive optimisation statistics ------------------------------------------
    def avg_gain(self, pass_name):
        gain, runs = self.data["pass_gain"].get(pass_name, [0, 0])
        return gain / runs if runs else 0.0

    def record_pass(self, pass_name, removed):
        g = self.data["pass_gain"].setdefault(pass_name, [0, 0])
        g[0] += removed
        g[1] += 1


# =====================================================================
# 1. AUTO ERROR DETECTION & FIXING
# =====================================================================
LEGAL = re.compile(r"[^A-Za-z0-9_=(),<>\s]")


def repair_source(source, log):
    """LEVEL 1 - character / token level repairs on the raw text."""
    out = []
    for n, line in enumerate(source.splitlines(), 1):
        bad = LEGAL.findall(line)
        if bad:
            line = LEGAL.sub("", line)
            log.append(("source", f"line {n}: removed illegal character(s) {''.join(sorted(set(bad)))!r}"))
        m = re.match(r"^(\s*)([A-Za-z_]+)(.*)$", line)
        if m:
            ind, word, rest = m.groups()
            fixed = None
            if word not in KEYWORDS and word.upper() in KEYWORDS and (word.islower() or word.istitle()):
                fixed = word.upper()
            elif word not in KEYWORDS and word.isupper():
                close = difflib.get_close_matches(word, sorted(KEYWORDS), n=1, cutoff=0.7)
                fixed = close[0] if close else None
            if fixed:
                log.append(("source", f"line {n}: keyword '{word}' -> '{fixed}'"))
                line = ind + fixed + rest
        # STEP action typo
        m = re.search(r"\bSTEP\s+([A-Za-z_]\w*)", line)
        if m and m.group(1) not in KNOWN_ACTIONS:
            close = difflib.get_close_matches(m.group(1), KNOWN_ACTIONS, n=1, cutoff=0.8)
            if close:
                log.append(("source", f"line {n}: action '{m.group(1)}' -> '{close[0]}'"))
                line = line[:m.start(1)] + close[0] + line[m.end(1):]
        # missing ()
        if re.match(r"^\s*(REPEAT\s+\d+\s+)?(STEP|CALL)\s+[A-Za-z_]\w*\s*$", line):
            log.append(("source", f"line {n}: added missing '()'"))
            line = line.rstrip() + "()"
        elif re.match(r"^\s*(REPEAT\s+\d+\s+)?(STEP|CALL)\s+[A-Za-z_]\w*\([^)]*$", line):
            log.append(("source", f"line {n}: added missing ')'"))
            line = line.rstrip() + ")"
        # missing '='
        m = re.match(r"^(\s*INGREDIENT\s+[A-Za-z_]\w*)\s+(\d+.*)$", line)
        if m:
            log.append(("source", f"line {n}: added missing '='"))
            line = f"{m.group(1)} = {m.group(2)}"
        out.append(line)
    return "\n".join(out) + "\n"


def _choose(mem, kind, options, applied):
    """Try the strategies in LEARNED order; the first one that works wins."""
    for name in mem.rank(kind, list(options)):
        result = options[name]()
        if result is not None:
            applied.append((kind, name))
            return name, result
    return None, None


def _bodies(ast):
    """(node_list, known_extra_names) for the main program and every procedure."""
    yield ast.steps, set()
    for p in ast.procedures:
        yield p.body, set(p.params)


def fix_ast_round(ast, mem, log, applied):
    """LEVEL 2 - meaning repairs. Returns True if anything changed."""
    changed = False
    note = lambda msg: log.append(("meaning", msg))

    if ast.serves is not None and ast.serves <= 0:
        note(f"SERVES {ast.serves} is invalid -> removed")
        ast.serves = None
        changed = True

    # duplicate ingredient declarations
    seen, keep = {}, []
    for ing in ast.ingredients:
        if ing.name in seen:
            first = seen[ing.name]
            if first.unit == ing.unit and first.quantity > 0 and ing.quantity > 0:
                first.quantity += ing.quantity
                note(f"duplicate '{ing.name}' merged (quantity now {first.quantity})")
                applied.append(("duplicate_ingredient", "merge"))
            else:
                note(f"duplicate '{ing.name}' dropped (kept the first declaration)")
                applied.append(("duplicate_ingredient", "drop"))
            changed = True
            continue
        seen[ing.name] = ing
        keep.append(ing)
    ast.ingredients = keep

    # non-positive quantities
    for ing in ast.ingredients:
        if ing.quantity <= 0:
            name, val = _choose(mem, "bad_quantity", {
                "learned_quantity": lambda: mem.typical_qty(ing.name, ing.unit),
                "default_one": lambda: 1,
            }, applied)
            note(f"quantity of '{ing.name}' was {ing.quantity} -> {val} (strategy: {name})")
            ing.quantity = val
            changed = True

    declared = {i.name for i in ast.ingredients}
    names_for_cook = lambda: [i.name for i in ast.ingredients]

    # nodes: repeat, time values, undeclared ingredients, bad CALLs
    procs = {p.name: p for p in ast.procedures}
    cyclic = {n for n in procs if _reaches(procs, n, n)}
    for nodes, extra in list(_bodies(ast)):
        owner = next((p.name for p in ast.procedures if p.body is nodes), None)
        i = 0
        while i < len(nodes):
            node = nodes[i]
            if node.repeat <= 0:
                note(f"REPEAT {node.repeat} -> 1")
                node.repeat = 1
                changed = True
            if isinstance(node, CallNode):
                proc = procs.get(node.name)
                if proc is None:
                    note(f"CALL to undefined procedure '{node.name}' removed")
                    nodes.pop(i); changed = True; continue
                if owner in cyclic and node.name in cyclic:
                    note(f"recursive CALL '{node.name}' inside '{owner}' removed")
                    nodes.pop(i); changed = True; continue
                if len(node.args) > len(proc.params):
                    note(f"CALL {node.name}: extra argument(s) dropped")
                    node.args = node.args[:len(proc.params)]
                    changed = True
                elif len(node.args) < len(proc.params):
                    note(f"CALL {node.name}: too few arguments -> call removed")
                    nodes.pop(i); changed = True; continue
            known = declared | extra
            j = 0
            while j < len(node.args):
                arg = node.args[j]
                if arg[0] == "time_value" and arg[1] <= 0:
                    exp = mem.expected_cook(names_for_cook(), exclude=ast.name)
                    name, val = _choose(mem, "bad_time", {
                        "learned_time": lambda: int(round(exp[0])) if exp else None,
                        "default_ten": lambda: 10,
                    }, applied)
                    note(f"time {arg[1]} {arg[2]} -> {val} minutes (strategy: {name})")
                    node.args[j] = ("time_value", val, "minutes")
                    changed = True
                elif arg[0] == "ingredient_ref" and arg[1] not in known:
                    bad = arg[1]

                    def fuzzy():
                        c = difflib.get_close_matches(bad, sorted(known), n=1, cutoff=0.72)
                        if c:
                            node.args[j] = ("ingredient_ref", c[0])
                            return f"renamed to '{c[0]}'"
                    def declare():
                        if bad in KB and owner is None:
                            unit = next(iter(KB[bad]["kcal"]), None)
                            q = mem.typical_qty(bad, unit) or 1
                            ast.ingredients.append(IngredientNode(bad, q, unit))
                            declared.add(bad)
                            return f"declared automatically as {q}{' ' + unit if unit else ''}"
                    def drop():
                        node.args.pop(j)
                        return "dropped from the step"
                    name, how = _choose(mem, "undeclared_ingredient", {
                        "fuzzy_rename": fuzzy, "declare_from_kb": declare, "drop_argument": drop}, applied)
                    note(f"'{bad}' is not declared -> {how} (strategy: {name})")
                    changed = True
                    if name == "drop_argument":
                        continue
                j += 1
            if isinstance(node, StepNode) and node.action == "add" and not node.args:
                note("empty add() removed")
                nodes.pop(i); changed = True; continue
            i += 1

    # procedures whose body became empty
    for p in list(ast.procedures):
        if not p.body:
            note(f"procedure '{p.name}' became empty -> removed")
            ast.procedures.remove(p)
            changed = True
    return changed


def auto_fix_meaning(ast, mem, log, applied):
    """Repeat level-2 repairs until the semantic analyzer is satisfied (fix-point)."""
    errors = []
    for _ in range(8):
        changed = fix_ast_round(ast, mem, log, applied)
        _, errors = SemanticAnalyzer(ast).analyze()
        if any("violates" in e.message for e in errors):
            fixed, changes = try_repair(ast)
            if fixed is not None:
                for c in changes:
                    log.append(("meaning", f"diet/allergen: {c}"))
                applied.append(("diet", "substitute"))
                ast = fixed
                changed = True
                _, errors = SemanticAnalyzer(ast).analyze()
        if not errors:
            break
        if not changed:
            break
    return ast, errors


def _flat(node, procs, bind=None, depth=0):
    """(action, [ingredient names]) for every primitive step a node expands to."""
    bind = bind or {}
    rn = lambda a: bind.get(a[1], a[1]) if a[0] == "ingredient_ref" else None
    if isinstance(node, StepNode):
        return [(node.action, [n for n in map(rn, node.args) if n])] * node.repeat
    proc = procs.get(node.name)
    if proc is None or depth > 8:
        return []
    b = dict(zip(proc.params, map(rn, node.args)))
    out = []
    for _ in range(node.repeat):
        for sub in proc.body:
            out += _flat(sub, procs, {k: v for k, v in b.items() if v}, depth + 1)
    return out


def fix_flow(ast, mem, log, applied):
    """LEVEL 3 - kitchen-flow repairs (order of the steps). Returns unfixed issues."""
    procs = {p.name: p for p in ast.procedures}
    note = lambda msg: log.append(("flow", msg))
    unfixed = []
    for _ in range(14):
        issue = None
        hot, contents, cooked, served = False, set(), False, False
        for i, node in enumerate(ast.steps):
            for act, names in _flat(node, procs):
                if served and act != "serve":
                    issue = ("after_serve", i); break
                if act in HEATERS:
                    hot = True; contents.update(names)
                elif act == "add":
                    if not hot:
                        issue = ("cold", i); break
                    contents.update(names)
                elif act == "cook":
                    if not hot:
                        issue = ("cold", i); break
                    if not contents:
                        issue = ("empty", i); break
                    cooked = True
                elif act == "serve":
                    if not cooked:
                        issue = ("early", i); break
                    served = True
            if issue:
                break
        if not issue:
            break
        kind, i = issue
        if kind == "cold":
            ast.steps.insert(i, StepNode("heat_pan", []))
            note(f"step {i + 1} needs heat -> inserted heat_pan() before it")
            applied.append(("flow", "insert_heat"))
        elif kind == "empty":
            used = {n for nd in ast.steps for _, ns in _flat(nd, procs) for n in ns}
            unused = [x.name for x in ast.ingredients if x.name not in used]
            if not unused:
                unfixed.append(f"step {i + 1}: cook() with nothing in the pan and no spare ingredient")
                break
            ast.steps.insert(i, StepNode("add", [("ingredient_ref", n) for n in unused]))
            note(f"cook() had an empty pan -> inserted add({', '.join(unused)}) "
                 f"(declared but never used)")
            applied.append(("flow", "add_unused"))
        elif kind == "early":
            later_cook = any(a == "cook" for nd in ast.steps[i + 1:] for a, _ in _flat(nd, procs))
            if later_cook:
                node = ast.steps.pop(i)
                ast.steps.append(node)
                note("serve() came before cooking finished -> moved to the end")
                applied.append(("flow", "move_serve"))
            else:
                exp = mem.expected_cook([x.name for x in ast.ingredients], exclude=ast.name)
                t = int(round(exp[0])) if exp else 10
                ast.steps.insert(i, StepNode("cook", [("time_value", t, "minutes")]))
                note(f"serve() with no cooking -> inserted cook({t} minutes) "
                     f"({'learned from similar recipes' if exp else 'default'})")
                applied.append(("flow", "insert_cook"))
        else:  # after_serve
            s = next(k for k, nd in enumerate(ast.steps)
                     if any(a == "serve" for a, _ in _flat(nd, procs)))
            node = ast.steps.pop(s)
            ast.steps.append(node)
            note("steps found after serve() -> serve() moved to the end")
            applied.append(("flow", "move_serve"))
    if not any(a == "serve" for nd in ast.steps for a, _ in _flat(nd, procs)):
        ast.steps.append(StepNode("serve", []))
        note("recipe never served -> appended serve()")
        applied.append(("flow", "append_serve"))
    return unfixed


# =====================================================================
# 2. REASONING - forward-chaining inference engine
# =====================================================================
class Rule:
    def __init__(self, name, requires, forbids, test, produce, why):
        self.name, self.requires, self.forbids = name, requires, forbids
        self.test, self.produce, self.why = test, produce, why


def _match(pattern, facts):
    return any(len(f) == len(pattern) and all(p == "*" or p == x for p, x in zip(pattern, f))
               for f in facts)


def build_rules():
    always = lambda c: True
    return [
        Rule("R1", [("action", "cook")], [], always, lambda c: [("cooked",)],
             "a cook() step exists"),
        Rule("R2", [("has", "rice"), ("cooked",)], [], always,
             lambda c: [("category", "rice dish")], "rice that is cooked makes a rice dish"),
        Rule("R3", [("has", "lentils"), ("cooked",)], [], always,
             lambda c: [("category", "lentil dish (dal / soup)")], "cooked lentils make a dal or soup"),
        Rule("R4", [("has", "egg")], [], always,
             lambda c: [("category", "egg dish")], "eggs are the main ingredient"),
        Rule("R5", [("has", "chicken"), ("cooked",)], [], always,
             lambda c: [("category", "chicken dish")], "cooked chicken makes a chicken dish"),
        Rule("R6", [("has", "potato"), ("cooked",)], [], always,
             lambda c: [("category", "potato dish")], "cooked potato makes a potato dish"),
        Rule("R7", [("category", "*")], [], always, lambda c: [("savory",)],
             "every recognised category here is a savoury dish"),
        Rule("R8", [("savory",)], [("has", "salt")], always,
             lambda c: [("suggest", "add salt (savoury dishes are normally salted)")],
             "a savoury dish without salt"),
        Rule("R9", [("cooked",)], [],
             lambda c: any(n in c["names"] and c["cook_min"] < m for n, m in MIN_COOK.items()),
             lambda c: [("undercooked", n, m) for n, m in MIN_COOK.items()
                        if n in c["names"] and c["cook_min"] < m],
             "total cooking time is below the minimum for an ingredient"),
        Rule("R10", [], [], lambda c: (c["cal_ps"] or 0) > 700,
             lambda c: [("heavy meal",)], "more than 700 kcal per serving"),
        Rule("R11", [], [("tag", "meat"), ("tag", "fish")], always,
             lambda c: [("naturally", "vegetarian")], "no meat or fish ingredient"),
        Rule("R12", [("naturally", "vegetarian")], [("tag", "dairy"), ("tag", "egg")], always,
             lambda c: [("naturally", "vegan")], "vegetarian and no dairy or egg"),
        Rule("R13", [("naturally", "vegan")], [], lambda c: c["diet"] is None,
             lambda c: [("suggest", "declare DIET vegan so the compiler guards it")],
             "recipe is vegan but declares no diet"),
        Rule("R14", [("naturally", "vegetarian")], [("naturally", "vegan")],
             lambda c: c["diet"] is None,
             lambda c: [("suggest", "declare DIET vegetarian so the compiler guards it")],
             "recipe is vegetarian but declares no diet"),
        Rule("R15", [], [], lambda c: c["prot_ps"] >= 20,
             lambda c: [("high protein",)], "20 g or more protein per serving"),
    ]


def reason(ast, metrics):
    """Returns (facts, derivations). derivations: fact -> (rule, premises, why)."""
    ir_names = {i.name for i in ast.ingredients}
    serves = ast.serves or 1
    ctx = {"names": ir_names, "cook_min": metrics["cook_time"], "diet": ast.diet,
           "cal_ps": metrics["calories"] / serves, "prot_ps": metrics["protein"] / serves}
    facts = set()
    for n in ir_names:
        facts.add(("has", n))
        for t in tags_of(n):
            facts.add(("tag", t))
    for node in ast.expanded_steps:
        facts.add(("action", node.action))
    base = set(facts)
    deriv = {}
    rules = build_rules()
    changed = True
    while changed:
        changed = False
        for r in rules:
            if not all(_match(p, facts) for p in r.requires):
                continue
            if any(_match(p, facts) for p in r.forbids):
                continue
            if not r.test(ctx):
                continue
            for f in r.produce(ctx):
                if f not in facts:
                    facts.add(f)
                    prem = [p for p in r.requires]
                    deriv[f] = (r.name, prem, r.why)
                    changed = True
    return facts - base, deriv


def raise_cook_time(ast, needed_min):
    """Reasoned decision: lengthen the last top-level cooking time to reach needed_min."""
    total = contracts.measure(ast)[0]["cook_time"]
    delta = needed_min - total
    for node in reversed(ast.steps):
        for k, arg in enumerate(node.args):
            if arg[0] == "time_value":
                old = arg[1] * contracts.TIME_TO_MIN[arg[2]]
                node.args[k] = ("time_value", int(math.ceil(old + delta)), "minutes")
                return True
    return False


# =====================================================================
# 4. ADAPTIVE OPTIMISATION (passes scheduled by learned profit)
# =====================================================================
def _reindex(ir):
    for k, ins in enumerate(ir, 1):
        ins.index = k
    return ir


def p_dedupe(ir):
    out, ch = [], []
    for ins in ir:
        if (out and not ins.resolved_args and not out[-1].resolved_args
                and ins.action == out[-1].action and ins.action in ("heat_pan", "serve")):
            ch.append(f"dropped repeated {ins.action}()")
            continue
        out.append(ins)
    return out, ch


def p_merge_cook(ir):
    out, ch = [], []
    for ins in ir:
        prev = out[-1] if out else None
        if (prev and ins.action == "cook" and prev.action == "cook"
                and len(prev.resolved_args) == 1 and len(ins.resolved_args) == 1
                and prev.resolved_args[0]["unit"] == ins.resolved_args[0]["unit"]):
            prev.resolved_args[0]["duration"] += ins.resolved_args[0]["duration"]
            ch.append(f"merged two cook() steps into cook({prev.resolved_args[0]['duration']} "
                      f"{prev.resolved_args[0]['unit']})")
            continue
        out.append(ins)
    return out, ch


def p_fuse_adds(ir):
    out, ch = [], []
    for ins in ir:
        prev = out[-1] if out else None
        if (prev and ins.action == "add" and prev.action == "add"
                and all(a["kind"] == "ingredient" for a in prev.resolved_args + ins.resolved_args)):
            prev.resolved_args = prev.resolved_args + ins.resolved_args
            ch.append("fused consecutive add() steps")
            continue
        out.append(ins)
    return out, ch


def p_dead_stir(ir):
    out, ch, contents = [], [], False
    for ins in ir:
        if ins.action in ("add", "boil") and any(a["kind"] == "ingredient" for a in ins.resolved_args):
            contents = True
        if ins.action == "stir" and not contents:
            ch.append("removed stir() on an empty pan")
            continue
        out.append(ins)
    return out, ch


PASSES = {"dedupe_idempotent": p_dedupe, "merge_cooks": p_merge_cook,
          "fuse_adds": p_fuse_adds, "dead_stir": p_dead_stir}


def smart_optimize(ir, mem=None, learn=True):
    """Runs all passes to a fix-point. The pass order comes from learned profit.
    Returns (optimized_ir, changes, info)."""
    mem = mem or Memory()
    order = sorted(PASSES, key=lambda p: -mem.avg_gain(p))
    cur = copy.deepcopy(ir)
    changes, gained, sweeps = [], {p: 0 for p in PASSES}, 0
    while True:
        sweeps += 1
        progress = False
        for name in order:
            cur, ch = PASSES[name](cur)
            if ch:
                progress = True
                gained[name] += len(ch)
                changes += [f"[{name}] {c}" for c in ch]
        if not progress or sweeps > 10:
            break
    if learn:
        for p, g in gained.items():
            mem.record_pass(p, g)
    return _reindex(cur), changes, {"order": order, "sweeps": sweeps, "gained": gained}


# =====================================================================
# DRIVER
# =====================================================================
def _clean_metrics(ast):
    table, errs = SemanticAnalyzer(ast).analyze()
    if errs:
        return None, None, errs
    metrics, _, ir = contracts.measure(ast)
    return metrics, ir, []


def train(mem, paths):
    """Learn from many recipes. Only recipes that compile cleanly are remembered."""
    learned = 0
    for p in paths:
        try:
            ast = parse_source(open(p, encoding="utf-8").read())
        except (LexicalError, SyntaxErrorRL):
            continue
        table, errs = SemanticAnalyzer(ast).analyze()
        if errs:
            continue
        ir = generate_ir(ast, table)
        if analyze_flow(ir)[0]:
            continue
        metrics = contracts.measure(ast)[0]
        mem.learn_recipe(ast, metrics["cook_time"])
        learned += 1
    return learned


def run_smart(source, mem=None, learn=True, out=print, show_opt=True):
    """The whole smart-compiler workflow. Returns (final_source, ast, ok)."""
    mem = mem or Memory()
    if len(mem.recipes) < 5 and os.path.isdir(CORPUS_DIR):
        n = train(mem, sorted(glob.glob(os.path.join(CORPUS_DIR, "*.recipe"))))
        out(f"  (first run: the compiler trained itself on {n} example recipes from corpus/)")
    log, applied = [], []

    # ---------------- 1. detect & fix ----------------
    out("\n  [1] AUTO ERROR DETECTION & FIXING")
    text = repair_source(source, log)
    try:
        ast = parse_source(text)
    except (LexicalError, SyntaxErrorRL) as e:
        out(f"      Level 1 (source): could not repair - {e}")
        for stage, msg in log:
            out(f"        fixed: {msg}")
        return source, None, False
    ast, errors = auto_fix_meaning(ast, mem, log, applied)
    flow_unfixed = []
    if not errors:
        flow_unfixed = fix_flow(ast, mem, log, applied)
        _, errors = SemanticAnalyzer(ast).analyze()

    # goals (ENSURE) - synthesis from contracts.py
    if not errors and ast.contracts:
        res = contracts.tune(ast, 0.5)
        if res["status"] == "ok":
            for e in contracts.describe_edits(res["dims"], res["state"]):
                log.append(("goal", f"ENSURE goals failed -> auto-tuned: {e}"))
            ast = res["new_ast"]
            _, errors = SemanticAnalyzer(ast).analyze()
        elif res["status"] != "already":
            flow_unfixed.append("ENSURE goals cannot be met within the edit limits")

    by_stage = {"source": "level 1 source text", "meaning": "level 2 meaning",
                "flow": "level 3 kitchen flow", "goal": "goals"}
    if log:
        for stage, msg in log:
            out(f"      FIXED ({by_stage[stage]}): {msg}")
    else:
        out("      no problems detected")

    final_ir = None
    if not errors:
        table, _ = SemanticAnalyzer(ast).analyze()
        final_ir = generate_ir(ast, table)
        flow_errors = analyze_flow(final_ir)[0]
    else:
        flow_errors = []
    remaining = [e.message for e in errors] + flow_errors + flow_unfixed
    if remaining:
        for r in remaining:
            out(f"      UNFIXED: {r}")
        for kind, opt in applied:
            mem.record(kind, opt, False) if learn else None
        if learn:
            mem.save()
        out("      RESULT: some problems could not be repaired automatically.")
        return source, ast, False
    out(f"      VERIFIED: the repaired program passes all checks "
        f"({len(log)} fix(es) applied, re-checked until clean).")

    # ---------------- 2. reasoning ----------------
    metrics, ir, _ = _clean_metrics(ast)
    out("\n  [2] REASONING ENGINE (forward chaining)")
    derived, why = reason(ast, metrics)
    reasoned_fix = False
    for _ in range(3):
        under = [f for f in derived if f[0] == "undercooked"]
        if not under:
            break
        need = max(f[2] for f in under)
        names = ", ".join(sorted({f[1] for f in under}))
        if raise_cook_time(ast, need):
            out(f"      DECISION: {names} needs at least {need} min but the recipe cooks "
                f"{metrics['cook_time']:.0f} min -> cooking time raised to {need} min")
            applied.append(("reasoning", "raise_time"))
            reasoned_fix = True
            _clean = _clean_metrics(ast)
            metrics, ir = _clean[0], _clean[1]
            derived, why = reason(ast, metrics)
    if not derived:
        out("      no conclusions could be derived")
    for fact in sorted(derived, key=lambda f: why[f][0]):
        rule, prem, reason_text = why[fact]
        label = " ".join(str(x) for x in fact)
        rule_obj = next(r for r in build_rules() if r.name == rule)
        pr = " & ".join(" ".join(p) for p in prem)
        if rule_obj.forbids:
            pr += (" & " if pr else "") + "absence of " + " / ".join(" ".join(p) for p in rule_obj.forbids)
        pr = pr or "numbers of this recipe"
        out(f"      {rule}: {label}")
        out(f"          because {reason_text}  [{pr}]")
    if reasoned_fix:
        log.append(("flow", "cooking time raised by reasoning"))

    # ---------------- 3. learning ----------------
    names = [i.name for i in ast.ingredients]
    out(f"\n  [3] LEARNING (memory holds {len(mem.recipes)} recipes)")
    exp = mem.expected_cook(names, exclude=ast.name)
    if exp:
        e, tol, n = exp
        cook = metrics["cook_time"]
        verdict = "typical" if abs(cook - e) <= tol else (
            "much longer than usual" if cook > e else "much shorter than usual")
        out(f"      cooking time {cook:.0f} min vs expected {e:.0f} +/- {tol:.0f} min "
            f"(from {n} similar recipes) -> {verdict}")
    else:
        out("      no similar recipes in memory yet - nothing to compare with")
    sugg = mem.associations(names, exclude=ast.name)
    for y, conf, sup, x, total in sugg[:3]:
        out(f"      SUGGESTION: add '{y}'? {round(conf * 100)}% of the {total} remembered "
            f"recipes with '{x}' also use it")
    if not sugg:
        out("      no missing-ingredient suggestions")

    # ---------------- 4. optimisation ----------------
    if show_opt:
        out("\n  [4] ADAPTIVE OPTIMISATION")
        ir = generate_ir(ast, SemanticAnalyzer(ast).analyze()[0])
        opt, changes, info = smart_optimize(ir, mem, learn)
        out(f"      pass order (most profitable first): {' > '.join(info['order'])}")
        for c in changes:
            out(f"        - {c}")
        if not changes:
            out("        - nothing to optimise")
        out(f"      RESULT: {len(ir)} -> {len(opt)} instructions in {info['sweeps']} sweep(s)")

    # the program is verified clean: every strategy used in this run succeeded
    if learn:
        for kind, opt in applied:
            mem.record(kind, opt, True)
    # ---------------- 5. adaptation ----------------
    out("\n  [5] ADAPTATION (how the compiler's own behaviour has changed)")
    shown = False
    for kind, stats in sorted(mem.data["strategy"].items()):
        ranked = mem.rank(kind, list(stats))
        txt = ", ".join(f"{o} {mem.rate(kind, o)[0]}/{mem.rate(kind, o)[1]}" for o in ranked)
        out(f"      fix strategy '{kind}' ranked by success: {txt}")
        shown = True
    if exp:
        out(f"      time tolerance for this recipe = {exp[1]:.1f} min "
            f"(shrinks as more similar recipes are learned)")
        shown = True
    if not shown:
        out("      nothing adapted yet (the compiler has no fix history)")

    # ---------------- finish ----------------
    final_source = unparse(ast) if (log or reasoned_fix) else source
    if learn:
        mem.learn_recipe(ast, metrics["cook_time"])
        mem.data["runs"] = mem.data.get("runs", 0) + 1
        mem.save()
    return final_source, ast, True


if __name__ == "__main__":
    args = sys.argv[1:]
    mem = Memory()
    if "--train" in args:
        folder = args[args.index("--train") + 1]
        n = train(mem, sorted(glob.glob(os.path.join(folder, "*.recipe"))))
        mem.save()
        print(f"Learned from {n} recipes. Memory now holds {len(mem.recipes)} recipes.")
        sys.exit(0)
    files = [a for a in args if not a.startswith("--")]
    path = files[0]
    src = open(path, encoding="utf-8").read()
    print("\n" + "#" * 64)
    print(f"  RecipeLang SMART COMPILER - {path}")
    print("#" * 64)
    final, ast, ok = run_smart(src, mem, learn="--no-learn" not in args)
    if ok and final != src:
        outp = path.rsplit(".", 1)[0] + "_smart.recipe"
        with open(outp, "w", encoding="utf-8") as f:
            f.write(final)
        print(f"\n  Corrected program saved to: {outp}\n")
        for i, line in enumerate(final.splitlines(), 1):
            print(f"    {i:>2} | {line}")
    print("\n  RESULT:", "compiled successfully" if ok else "could not be fully repaired")
