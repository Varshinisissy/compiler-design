# Novelty feature: Recipe Contracts + Goal-Directed Auto-Tuner

New language constructs (header lines, any order):

    PROTECT lentils                       # tuner must never change this ingredient
    ENSURE calories_per_serving <= 600    # goals the finished dish must meet
    ENSURE protein_per_serving  >= 22
    ENSURE cook_time            <= 20 minutes

Metrics: calories, calories_per_serving, protein, protein_per_serving, cook_time.
Operators: <= >= < > ==  (per_serving metrics need SERVES).

What the compiler does
1. VERIFY   - checks every ENSURE against the optimized IR (static contract checking).
2. BLAME    - for a failing goal, shows which ingredients / steps cause it.
3. SYNTHESISE - uniform-cost search over small edits (quantity +/-, cook time +/-,
   ingredient swap) finds the CHEAPEST recipe that meets all goals (verified against
   brute force on the samples). Diet / AVOID rules are respected for swaps.
4. PROVE    - the tuned program is re-run through the real pipeline and re-verified,
   then written out as <name>_tuned.recipe.
5. If impossible, it says so and shows the closest attempt.

Run
    python demo.py goals_protein.recipe --fast        # full pipeline incl. tuner
    python contracts.py goals_light.recipe --write    # tuner only, saves *_tuned.recipe
    python contracts.py goals_impossible.recipe --limit 80   # allow bigger edits

Samples: goals_light, goals_protein, goals_proc (CALL arguments), goals_met (already
valid), goals_impossible (infeasible), goals_bad (new semantic rules 9 and 10).

Files: contracts.py (new), knowledge.py (+protein, +alternatives), lexer/parser
(ENSURE, PROTECT, OP tokens), semantic_analyzer.py (rules 9-10), repair.py (unparse),
demo.py (new stage). Also fixed a crash in main.py for recipes that use CALL.

---

# Smart compiler (smart.py)

A compiler that goes beyond ordinary compilation: reasoning, optimisation, learning,
adaptive behaviour and automatic error detection + fixing.

| Technique | What it does |
|---|---|
| Auto error detection & fixing | 3 levels. (1) source text: illegal characters, misspelt keywords (`INGREDIANT`), lower-case keywords, missing `()` / `=`. (2) meaning: undeclared ingredient (typo -> rename, else declare from knowledge base, else drop), duplicates (merge), zero/negative quantity and time (learned value), bad CALL / recursion, diet violations. (3) kitchen flow: cold pan, empty pan, serve too early, steps after serve, missing serve. Fixes are applied in a loop and the whole program is re-verified. |
| Reasoning | Forward-chaining IF-THEN engine (15 rules) that derives facts (dish category, savoury, naturally vegan ...) with a "because" chain. Some conclusions trigger decisions, e.g. rice cooked < 10 min -> cooking time raised. |
| Learning | `smart_memory.json` stores every recipe the compiler has seen (pre-trained on `corpus/`, 17 recipes). It learns typical quantities, typical cooking time of similar recipes and ingredient associations (suggests missing ingredients, flags unusual cooking times). |
| Adaptive optimisation | Optimisation passes (dedupe, merge cooks, fuse adds, dead stir) are scheduled by their learned profit. |
| Adaptive strategy choice | Fix strategies (e.g. fuzzy-rename vs declare-from-KB) are ranked by their learned success rate, so behaviour changes with experience. |

Run
    python smart.py smart_broken.recipe            # full smart report + saves *_smart.recipe
    python smart.py any.recipe --no-learn          # do not update the memory
    python smart.py --train corpus                 # re-train from a folder
    python demo.py smart_broken.recipe --fast --smart   # smart stage + normal pipeline on the corrected program

ENSURE goals from the contract feature are also enforced: if they fail, the smart
compiler calls the auto-tuner. The memory is small (17 seed recipes), so suggestions
are only as good as the examples it has seen.
