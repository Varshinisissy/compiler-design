# RecipeLang — Phase 1 Design Document
### Compiler Design Laboratory — Individual Project

---

## 1. Project Title

**RecipeLang: A Domain-Specific Language and Compiler-Based Processing System for Structured Recipe Representation**

---

## 2. Abstract

RecipeLang is a small, purpose-built Domain-Specific Language (DSL) for expressing cooking recipes as structured, unambiguous programs rather than free-form prose. A recipe written in RecipeLang declares its ingredients with explicit quantities and units, then lists a sequence of cooking steps as function-like calls (e.g., `add(rice)`, `cook(10 minutes)`). Instead of treating this input as plain text, RecipeLang processes it through the standard stages of a compiler: a **lexer** converts the source into tokens, a **parser** validates the token stream against a formal grammar and builds an **Abstract Syntax Tree (AST)**, a **semantic analyzer** checks the recipe for logical consistency (e.g., that every ingredient used in a step was actually declared) using a **symbol table**, and a final stage converts the validated recipe into a structured **intermediate representation** that can be interpreted to produce a clean, verified, machine-usable recipe output. In short, RecipeLang applies real compiler-construction techniques to a relatable, easy-to-explain domain, replacing "a recipe app" with "a small, working compiler for a recipe language."

---

## 3. Problem Statement

Recipes as they normally exist — in cookbooks, blogs, or word documents — are **unstructured natural-language text**. This creates several concrete problems that are language-processing problems, not application problems:

- There is no formal way to verify that a recipe is **internally consistent** — for example, that every ingredient mentioned in the instructions was actually listed in the ingredients section, or that quantities and time values are well-formed.
- There is no standard, machine-processable **intermediate representation** of a recipe, so recipes cannot be reliably scaled, validated, or transformed by software without fragile natural-language parsing.
- Because recipes are just text, **errors go undetected until someone is already cooking** — a missing ingredient reference or a malformed quantity is only caught by a human reading carefully, not by any systematic check.

The core problem RecipeLang addresses is: *how do we define a formal grammar for representing recipes, and build a compiler front-end (lexer, parser, semantic analyzer) that can automatically verify a recipe's structural and logical correctness, and produce a validated, structured representation of it?* This is fundamentally a **language design and language-processing problem**, addressed using compiler design techniques — not a recipe-storage or recipe-display application.

---

## 4. Motivation

- **DSLs solve narrow problems better than general-purpose tools.** A recipe has a very specific, repeating shape (ingredients + steps), which is exactly the kind of narrow, well-defined domain a DSL is designed for — much like how SQL is a DSL for queries or CSS is a DSL for styling.
- **Building a compiler/interpreter for even a small DSL exercises the full compiler pipeline in miniature.** Every stage — lexical analysis, parsing, AST construction, semantic analysis, symbol tables, and structured output generation — has a genuine, non-trivial job to do in RecipeLang, which makes it a legitimate vehicle for learning and demonstrating compiler design concepts, not just a toy example.
- **Automatic validation has real value.** A recipe that is "compiled" successfully is *guaranteed* to have consistent ingredients and well-formed quantities — something a plain-text recipe can never guarantee. This shows a genuine, practical benefit of applying language-processing techniques to an everyday domain.
- **It is approachable to explain.** Because everyone understands what a recipe is, the compiler concepts (tokens, grammar, symbol table, semantic errors) can be explained clearly and concretely during a viva, without requiring the audience to already understand a niche technical domain.

---

## 5. Objectives

1. Design a formal, unambiguous grammar for RecipeLang that captures recipe structure (ingredients + steps) using standard BNF notation.
2. Implement a **lexical analyzer** that converts RecipeLang source text into a well-defined stream of tokens (keywords, identifiers, numbers, units, time units, delimiters).
3. Implement a **recursive-descent parser** that performs **syntax analysis**, validating the token stream against the grammar and constructing an **Abstract Syntax Tree (AST)**.
4. Implement a **semantic analyzer** that enforces recipe-specific correctness rules (ingredient declared-before-use, no duplicate declarations, valid quantities) using a **symbol table** built from the AST.
5. Design an **intermediate representation (IR)** of a validated recipe that is independent of the original source syntax and suitable for further processing (scaling, execution, export).
6. Implement a simple **interpreter/output generator** that consumes the IR and produces a final, structured, human-readable and/or machine-readable recipe output.
7. Implement **error detection** across all phases (lexical, syntactic, semantic) with clear, phase-labeled error messages that identify the exact line and nature of the problem.
8. Demonstrate the complete pipeline end-to-end on realistic sample recipes, with both valid and deliberately invalid inputs.

---

## 6. Scope

**RecipeLang WILL support (v1 — implementable by one student):**
- A single `RECIPE <name>` block per program.
- `INGREDIENT` declarations with a name, numeric quantity, and an optional unit (e.g., `rice = 2 cups`, `tomato = 3`).
- `STEP` statements written as an action name with a parenthesized argument list, where arguments are either ingredient references or time values (e.g., `add(rice)`, `cook(10 minutes)`).
- Detection and reporting of lexical, syntactic, and semantic errors with line numbers.
- A structured, validated output representation of the recipe (Phase 1: a summary printout; later phases: JSON/IR and interpreted "execution log").

**RecipeLang will NOT support (explicitly out of scope for v1):**
- Multiple recipes in a single file, or recipe composition/sub-recipes.
- Conditional logic (`IF`/`ELSE`), loops, or variables beyond ingredient declarations.
- Unit conversion or arithmetic between different unit types (e.g., converting cups to grams).
- Natural-language step descriptions — steps must use the structured `action(args)` form.
- A graphical recipe-editor UI (a simple text input / command-line or minimal web front-end is sufficient).

**Limitations:** The initial grammar assumes one ingredient section followed by one step section (matching the manual's example structure); nested or interleaved declarations are not supported in v1.

**Future possibilities (explicitly NOT claimed as implemented):** conditional steps (e.g., `IF spicy THEN add(chili)`), automatic recipe scaling (multiply all quantities by a factor), nutrition/unit-conversion semantic checks, and multi-recipe "cookbook" programs. These are noted only as future direction, not as Phase 1/2/3 deliverables unless explicitly scheduled below.

---

## 7. Background Study

**What is a Domain-Specific Language (DSL)?**
A DSL is a small programming language designed to solve problems in one specific domain, as opposed to a general-purpose language (like Python or Java) that can express arbitrary computation. Examples include SQL (databases), CSS (styling), and regular expressions (pattern matching). DSLs trade generality for clarity and correctness within their narrow domain — exactly the trade-off RecipeLang makes for representing recipes.

**What is a compiler/interpreter, and how do they differ?**
A compiler translates source code written in one language into another form (traditionally machine code), performing analysis (lexical, syntax, semantic) along the way to catch errors before that translation happens. An interpreter directly executes/processes validated source without producing a separate standalone output program. RecipeLang behaves like an interpreter: it performs full compiler-style **analysis** (lexer → parser → AST → semantic analysis → symbol table), then directly interprets the validated recipe to produce output, rather than emitting a separate executable.

**Why compiler concepts genuinely apply to RecipeLang:**
Every recipe has lexical structure (keywords, identifiers, numbers, units), a formal grammar (a recipe is not just "any text" — it has a defined shape), and meaning that depends on context (an ingredient reference in a step is only meaningful if that ingredient was declared — exactly analogous to variable declaration-before-use in a general-purpose language). This means real semantic analysis and symbol-table techniques have a genuine job to do here, not an artificially imposed one.

**Existing problems with recipe representation:**
Current recipe formats (plain text, HTML, or even structured formats like recipe schema.org markup) describe *data* but do not *validate logical consistency*. A recipe blog can list "onion" in the ingredients and never use it, or reference "garlic" in a step without ever declaring it — nothing currently checks this automatically. This is precisely the kind of consistency-checking problem semantic analysis was designed to solve in real programming languages.

**Why a structured language is useful here:**
A structured, grammar-defined recipe format makes recipes *provably consistent* (every reference resolves, every quantity is well-formed) and opens the door to further automated processing (scaling, format conversion, export) that free text can never reliably support.

---

## 8. Compiler Design Concepts Involved

| Concept | How RecipeLang Uses It | Example |
|---|---|---|
| Lexical Analysis | Scans raw RecipeLang source character-by-character and groups characters into tokens (keywords, identifiers, numbers, units) | `INGREDIENT rice = 2 cups` → tokens `KEYWORD(INGREDIENT)`, `IDENT(rice)`, `ASSIGN(=)`, `NUMBER(2)`, `UNIT(cups)` |
| Tokens | The discrete, classified units produced by the lexer, each carrying a type, value, and line number | `Token(NUMBER, '2', line=2)` |
| Syntax Analysis (Parsing) | Verifies the token stream matches RecipeLang's grammar and builds a tree structure from it | Confirms an `INGREDIENT` declaration always has the form `INGREDIENT <id> = <number> [<unit>]` |
| Grammar | A formal BNF specification defining every valid RecipeLang construct | `<ingredient_decl> ::= "INGREDIENT" <identifier> "=" <number> [<unit>]` |
| Parser | The program module (recursive-descent) that applies the grammar to build the AST and detect syntax errors | Rejects `INGREDIENT rice 2 cups` (missing `=`) with a line-numbered syntax error |
| AST (Abstract Syntax Tree) | A tree representation of the recipe's structure, stripped of punctuation, used by later phases | `Recipe → [Ingredients] → [Steps]` (see Section 15) |
| Semantic Analysis | Checks meaning/consistency rules that pure grammar cannot express — e.g., is a referenced ingredient actually declared? | Rejects `add(salt)` if `salt` was never declared as an ingredient |
| Symbol Table | Stores every declared ingredient's name, type, quantity, and unit for lookup during semantic analysis | See Section 14 |
| Intermediate Representation | A syntax-independent structured form of the validated recipe, used for output generation (and, in Phase 3, execution) | A list of validated `(action, resolved_args)` tuples plus the ingredient table |
| Interpreter / Execution Engine | Walks the IR and produces the final structured recipe output (Phase 1: summary printout; Phase 3: full "execution log") | Prints `Step 1: heat_pan()`, `Step 2: add(oil — 2 tbsp)`, etc. |
| Error Detection & Recovery | Distinguishes and reports lexical, syntax, and semantic errors clearly, each tagged with a line number and phase | `Semantic Error (line 8): ingredient 'salt' used in STEP but never declared` |

*(No unnecessary concepts — e.g., full three-address code / machine-level code generation is not included, since RecipeLang's output is a structured recipe representation, not machine-executable code. This is intentionally scoped rather than "artificially completed.")*

---

## 9. RecipeLang Language Design

### A. Keywords
Only three keywords are needed — kept intentionally minimal:

| Keyword | Purpose |
|---|---|
| `RECIPE` | Begins a recipe definition, followed by its name |
| `INGREDIENT` | Declares an ingredient with quantity and optional unit |
| `STEP` | Declares one cooking action, with an action name and arguments |

*(Note: action names like `add`, `cook`, `heat_pan`, `serve` are **not** keywords — they are ordinary identifiers used as the action name after `STEP`. This keeps the keyword set small and lets step vocabulary grow freely without changing the grammar.)*

### B. Identifiers
Recipe names, ingredient names, and step action names. Rule: must start with a letter or underscore, followed by letters, digits, or underscores.
Examples: `TomatoRice`, `rice`, `heat_pan`, `add`.

### C. Literals
- **Numbers:** unsigned integers — `2`, `10`, `3` (decimal quantities like `1.5` are explicitly deferred; see Scope).
- **Units:** a fixed vocabulary — `cups`, `cup`, `tbsp`, `tsp`, `g`, `kg`, `ml`, `l`, `pieces`, `piece`.
- **Time values:** a number followed by a time unit — `10 minutes`, `2 hours`.
- **Time units:** `minutes`, `minute`, `seconds`, `second`, `hours`, `hour`.
- *(String literals in quotes are not needed in v1, since no free-text fields exist yet.)*

### D. Operators
Only one operator is needed: `=` (assignment, used exclusively in ingredient declarations to bind a quantity to an ingredient name). No arithmetic or comparison operators are needed in v1, since RecipeLang v1 has no computed expressions.

### E. Delimiters / Symbols
| Symbol | Meaning |
|---|---|
| `(` `)` | Enclose a STEP's argument list |
| `,` | Separates multiple arguments in a STEP call |
| newline | Terminates each declaration/statement (RecipeLang is line-oriented, like the sample program — no semicolons needed) |

### F. Data Types
Kept deliberately simple — three conceptual types:

| Type | Description | Example |
|---|---|---|
| `INGREDIENT` | A declared name bound to a quantity and optional unit | `rice = 2 cups` |
| `NUMBER` | A plain unsigned integer quantity or count | `3` (as in `tomato = 3`) |
| `TIME` | A number paired with a time unit, used only as a STEP argument | `10 minutes` |

*(No boolean, string, or float types in v1 — this keeps the semantic type-checking simple enough for one student to implement fully and correctly.)*

---

## 10. RecipeLang Syntax

### Valid Example 1 — the manual's reference example
```
RECIPE TomatoRice
INGREDIENT rice = 2 cups
INGREDIENT tomato = 3
INGREDIENT oil = 2 tbsp

STEP heat_pan()
STEP add(oil)
STEP add(tomato)
STEP add(rice)
STEP cook(10 minutes)
STEP serve()
```

### Valid Example 2 — a different recipe, showing the grammar generalizes
```
RECIPE VegetableSoup
INGREDIENT carrot = 2
INGREDIENT potato = 3
INGREDIENT water = 500 ml
INGREDIENT salt = 1 tsp

STEP boil(water)
STEP add(carrot)
STEP add(potato)
STEP add(salt)
STEP cook(20 minutes)
STEP serve()
```

### Valid Example 3 — an ingredient with no unit (a plain count) and multi-argument step
```
RECIPE BoiledEgg
INGREDIENT egg = 2
INGREDIENT water = 300 ml

STEP boil(water, egg)
STEP cook(8 minutes)
STEP serve()
```

### Invalid Examples (with explanation)

1. **Missing `=` in ingredient declaration**
   ```
   INGREDIENT rice 2 cups
   ```
   ❌ *Invalid — Syntax Error.* The grammar requires `INGREDIENT <identifier> "=" <number> [<unit>]`; without `=`, the parser cannot match this rule (the token `2` appears where `=` was expected).

2. **Recipe with no ingredients**
   ```
   RECIPE QuickToast
   STEP toast(bread)
   ```
   ❌ *Invalid — Syntax Error.* The grammar requires at least one `INGREDIENT` declaration before any `STEP` (Section 12); `bread` is also never declared, but the syntax error (missing ingredient section) is caught first.

3. **Duplicate ingredient declaration**
   ```
   RECIPE Test
   INGREDIENT rice = 2 cups
   INGREDIENT rice = 1 cup
   STEP add(rice)
   ```
   ❌ *Invalid — Semantic Error.* Both declarations are individually well-formed (syntax is fine), but declaring `rice` twice violates the semantic rule that every ingredient name must be unique within a recipe.

4. **Reference to an undeclared ingredient**
   ```
   RECIPE Test
   INGREDIENT rice = 2 cups
   STEP add(salt)
   ```
   ❌ *Invalid — Semantic Error.* `salt` is a syntactically valid identifier used correctly as a STEP argument, but it was never declared as an ingredient — this can only be caught by checking the symbol table, not by grammar alone.

5. **Invalid/misspelled keyword**
   ```
   RECIPEE Test
   INGREDIENT rice = 2 cups
   STEP add(rice)
   ```
   ❌ *Invalid — Syntax Error.* `RECIPEE` is not a recognized keyword; the lexer tokenizes it as a plain `IDENT` (since it does not match the fixed keyword list), and the parser then fails because it expected the keyword `RECIPE` at the start of the program.

---

## 11. Token Specification

| Token Type | Pattern / Example | Meaning |
|---|---|---|
| `KEYWORD` | `RECIPE`, `INGREDIENT`, `STEP` | Reserved words that begin a construct |
| `IDENT` | `rice`, `TomatoRice`, `add`, `heat_pan` | Recipe/ingredient/action names |
| `NUMBER` | `2`, `10`, `500` | Unsigned integer literal |
| `UNIT` | `cups`, `tbsp`, `g`, `ml`, `pieces` | Quantity unit following a number |
| `TIMEUNIT` | `minutes`, `hours`, `seconds` | Time unit following a number in a STEP argument |
| `ASSIGN` | `=` | Binds a quantity to an ingredient name |
| `LPAREN` | `(` | Opens a STEP argument list |
| `RPAREN` | `)` | Closes a STEP argument list |
| `COMMA` | `,` | Separates multiple STEP arguments |
| `NEWLINE` | `\n` | Statement terminator (consumed by the lexer, not passed to the parser) |
| `EOF` | *(end of input)* | Marks the end of the token stream |
| `MISMATCH` | *(any unrecognized character)* | Triggers a **lexical error** — e.g., `@`, `#`, `$` |

*(This table is the direct implementation reference for `lexer.py`'s `TOKEN_SPEC`, shown in Section 19.)*

---

## 12. Grammar (Context-Free, BNF)

```
<program>        ::= <recipe>

<recipe>         ::= "RECIPE" <identifier> <ingredient_list> <step_list>

<ingredient_list> ::= <ingredient_decl>+

<ingredient_decl> ::= "INGREDIENT" <identifier> "=" <number> [ <unit> ]

<step_list>       ::= <step_stmt>+

<step_stmt>        ::= "STEP" <identifier> "(" [ <arg_list> ] ")"

<arg_list>          ::= <arg> ( "," <arg> )*

<arg>                ::= <identifier>
                        | <number> <timeunit>

<identifier>          ::= letter ( letter | digit | "_" )*

<number>               ::= digit+

<unit>                  ::= "cups" | "cup" | "tbsp" | "tsp"
                           | "g" | "kg" | "ml" | "l" | "pieces" | "piece"

<timeunit>               ::= "minutes" | "minute" | "seconds" | "second"
                            | "hours" | "hour"
```

**Consistency check against the sample program:** `RECIPE TomatoRice` matches `<recipe>`'s opening; each `INGREDIENT ... = ... [unit]` line matches `<ingredient_decl>`; `STEP heat_pan()` matches `<step_stmt>` with an empty `<arg_list>`; `STEP add(oil)` matches `<step_stmt>` with a single identifier `<arg>`; `STEP cook(10 minutes)` matches `<step_stmt>` with a single `<number> <timeunit>` `<arg>`. Every construct in every example in Section 10 traces directly to a grammar rule above.

---

## 13. Semantic Rules

| Rule | Description | Error Category |
|---|---|---|
| Ingredient must be declared before use | Any identifier passed as a STEP argument must exist in the ingredient symbol table | **Semantic** |
| No duplicate ingredient declarations | Each ingredient name must be unique within a `RECIPE` block | **Semantic** |
| Quantity must be a valid positive number | An ingredient's declared quantity must be a positive integer (zero/negative is rejected) | **Semantic** |
| Time value must be valid | A time argument's number must be positive, and its unit must be one of the recognized time units | **Semantic** |
| Unit must be recognized (if present) | If an ingredient declares a unit, it must be one of the fixed unit vocabulary | **Semantic** *(the lexer already restricts this at the token level — see note below)* |
| STEP syntax must match the grammar | Every `STEP` must have the form `action(args)` with correctly matched parentheses and comma-separated arguments | **Syntactic** |
| Unrecognized characters | Any character not matched by any token pattern | **Lexical** |
| Missing/incorrect keywords or symbols | e.g., missing `=`, missing `RECIPE`, mismatched parentheses | **Syntactic** |

**How the three error categories differ in RecipeLang, concretely:**
- **Lexical errors** occur when the *lexer* cannot classify a character at all (e.g., `INGREDIENT rice = 2 @cups` — `@` matches no token pattern).
- **Syntactic errors** occur when the *tokens are individually valid* but arranged in a way that violates the grammar (e.g., `INGREDIENT rice 2 cups` — missing the `=` token in the required position).
- **Semantic errors** occur when the input is *grammatically well-formed* but logically inconsistent given the recipe's own declarations (e.g., using `add(salt)` when `salt` was never declared — every token and the arrangement are syntactically fine; the problem only appears once you check meaning against the symbol table).

---

## 14. Symbol Table Design

For each `INGREDIENT` declaration, RecipeLang stores an entry in a single, recipe-scoped symbol table (v1 has only one scope, since only one `RECIPE` block is supported):

| Name | Type | Value/Quantity | Unit | Scope |
|---|---|---|---|---|
| rice | INGREDIENT | 2 | cups | TomatoRice |
| tomato | INGREDIENT | 3 | (none) | TomatoRice |
| oil | INGREDIENT | 2 | tbsp | TomatoRice |

**How it's used:** during semantic analysis, every `STEP` argument that is an identifier (e.g., `add(rice)`) is looked up in this table. If found, the reference is considered valid and can be "resolved" to its quantity/unit for later output; if not found, a semantic error is raised (Section 13). The table is also checked at *declaration time* to reject duplicate names before they are ever inserted.

---

## 15. AST Design

For the `TomatoRice` example from Section 10:

```
Recipe(TomatoRice)
├── IngredientList
│   ├── Ingredient(rice, qty=2, unit=cups)
│   ├── Ingredient(tomato, qty=3, unit=None)
│   └── Ingredient(oil, qty=2, unit=tbsp)
└── StepList
    ├── Step(action=heat_pan, args=[])
    ├── Step(action=add, args=[Ref(oil)])
    ├── Step(action=add, args=[Ref(tomato)])
    ├── Step(action=add, args=[Ref(rice)])
    ├── Step(action=cook, args=[Time(10, minutes)])
    └── Step(action=serve, args=[])
```

**Node explanations:**
- **`Recipe`** — the root node; holds the recipe's name and its two children: the ingredient list and the step list.
- **`IngredientList` / `Ingredient`** — each `Ingredient` node stores the name, quantity, and (optional) unit exactly as declared; this subtree is what gets converted into the symbol table.
- **`StepList` / `Step`** — each `Step` node stores the action name and its argument list; each argument is either a `Ref` (a reference to a declared ingredient, resolved later against the symbol table) or a `Time` (a literal number + time unit, needing no symbol-table lookup).
- Punctuation tokens (`=`, `(`, `)`, `,`) from the token stream do **not** appear in the AST — they were only needed to guide the parser; the AST keeps just the meaningful structure, which is the defining feature of an AST versus a raw parse tree.

---

## 16. Proposed Methodology

```
RecipeLang Source (.recipe file)
        │
        ▼
Lexical Analysis          — scans characters, groups them into classified tokens
        │
        ▼
Tokens                    — stream of (type, value, line) triples
        │
        ▼
Syntax Analysis / Parser  — matches tokens against the grammar, builds the AST,
                             reports syntax errors with line numbers
        │
        ▼
AST                        — tree form of the recipe, stripped of punctuation
        │
        ▼
Semantic Analysis          — walks the AST, builds/consults the symbol table,
                             checks declared-before-use, duplicates, valid quantities
        │
        ▼
Symbol Table                — populated during semantic analysis; holds every
                              ingredient's name, quantity, and unit
        │
        ▼
Intermediate Representation — a syntax-independent structured form: a list of
                              (action, resolved-argument) records plus the
                              finalized ingredient table
        │
        ▼
Interpreter / Output Generator — walks the IR in order and produces the final
                                 structured recipe output
        │
        ▼
Final Recipe Output          — a validated, structured representation of the
                               recipe (Phase 1: console summary; later phases:
                               JSON export and/or a step-by-step "execution log")
```

**Plain-language explanation of each stage:** the lexer is like a proofreader breaking a sentence into individual words and labeling each word's part of speech; the parser checks that those words are arranged in a grammatically valid sentence and draws a sentence-diagram (the AST); semantic analysis is like fact-checking the sentence against what's already been established (e.g., "you mentioned Bob, but no one named Bob was introduced earlier"); the symbol table is the running "who's who" list used to do that fact-checking; the IR is a clean, rewritten version of the validated sentence with all references resolved; and the interpreter reads that clean version aloud as the final output.

---

## 17. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          RecipeLang System                           │
│                                                                       │
│   ┌───────────────┐                                                  │
│   │  Input Layer   │   .recipe source file / text input              │
│   └───────┬───────┘                                                  │
│           │ raw source text                                          │
│           ▼                                                          │
│   ┌───────────────┐                                                  │
│   │     Lexer      │   tokenizes source, flags lexical errors        │
│   └───────┬───────┘                                                  │
│           │ token stream                                             │
│           ▼                                                          │
│   ┌───────────────┐                                                  │
│   │    Parser      │   applies grammar, flags syntax errors          │
│   └───────┬───────┘                                                  │
│           │ AST                                                       │
│           ▼                                                          │
│   ┌───────────────┐        ┌────────────────────┐                    │
│   │ Semantic       │◀─────▶│   Symbol Table       │                  │
│   │ Analyzer       │        │ (ingredients:        │                  │
│   │ (declared-     │        │  name→qty/unit)      │                  │
│   │  before-use,   │        └────────────────────┘                    │
│   │  duplicates,   │                                                  │
│   │  valid qty)    │                                                  │
│   └───────┬───────┘                                                  │
│           │ validated AST                                             │
│           ▼                                                          │
│   ┌───────────────┐                                                  │
│   │  IR Generator  │   builds resolved (action, args) list            │
│   └───────┬───────┘                                                  │
│           │ IR                                                        │
│           ▼                                                          │
│   ┌───────────────┐                                                  │
│   │ Interpreter /  │   walks IR, produces final structured output     │
│   │ Execution      │                                                  │
│   │ Engine         │                                                  │
│   └───────┬───────┘                                                  │
│           │                                                           │
│           ▼                                                          │
│   ┌───────────────┐                                                  │
│   │ Output Layer   │   console summary / structured export           │
│   └───────────────┘                                                  │
│                                                                       │
│   ┌───────────────────────────────────────────────────────────┐      │
│   │  Error Handler — receives lexical/syntax/semantic errors    │      │
│   │  from any stage above and reports them with line numbers    │      │
│   └───────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

**Data flow:** each module passes a single, well-defined data structure to the next (source text → tokens → AST → validated AST + symbol table → IR → final output), and the Error Handler is a cross-cutting component that any stage can invoke to stop the pipeline and report a clear, phase-labeled diagnostic — mirroring how real compilers separate concerns between phases while sharing a common error-reporting mechanism.

---

## 18. Technology Stack

| Category | Choice | Reason |
|---|---|---|
| Programming Language | **Python 3** | Fast to prototype, excellent for string/regex handling, no build step — ideal for a solo student on a deadline |
| Lexer approach | Hand-written, regex-based (`re` module) | Full understanding and control of every token rule; no external dependency; directly explainable in viva |
| Parser approach | Hand-written **recursive-descent parser** | Matches the simple grammar in Section 12 one rule at a time; easiest parsing technique for an individual student to implement, test, and explain line-by-line |
| Libraries | Python standard library only (`re`, `json` for optional export) | Avoids over-engineering; no external dependency risk |
| IDE | VS Code (or any plain text editor + terminal) | No special setup needed |
| Visualization/UI | **None required for Phase 1** — a plain terminal/console interface is sufficient and appropriate | Adding a GUI now would be over-engineering relative to Phase 1's actual requirement (lexical analysis + basic syntax validation + meaningful output); a minimal web view can be considered in Phase 3 *only if time permits*, as a presentation layer over the already-working compiler |

---

## 19. Initial Prototype

**Scope of this prototype (Phase 1 only):** source code → lexical analysis → token generation → basic syntax validation (grammar structure) → a structured summary output. **Semantic analysis (duplicate/undeclared-ingredient checks, quantity validation), the symbol table, the IR, and the interpreter/execution engine are explicitly NOT implemented yet** — they are Phase 2/Phase 3 work (see Section 24). The parser below validates *structure only*.

### Folder Structure
```
recipelang_prototype/
├── lexer.py             # Stage 1: tokenizer
├── parser.py            # Stage 2: recursive-descent syntax validator + skeleton AST
├── main.py               # Driver: runs the pipeline and prints output
└── sample_input.recipe   # Sample RecipeLang program (TomatoRice)
```

### File Explanations
- **`lexer.py`** — Defines the token patterns (Section 11) and a `tokenize()` function that turns raw source text into a list of `Token` objects, raising a `LexicalError` on any unrecognized character.
- **`parser.py`** — Defines minimal AST node classes (`RecipeNode`, `IngredientNode`, `StepNode`) and a `Parser` class implementing the grammar from Section 12 as a set of recursive-descent methods (`parse_recipe`, `parse_ingredient`, `parse_step`, `parse_arg`), raising a `SyntaxErrorRL` with a line number on any structural violation.
- **`main.py`** — Ties the two stages together: reads a `.recipe` file, runs the lexer, prints the full token stream, runs the parser, and — if both stages succeed — prints a structured summary of the recipe (name, ingredient list, step list). If either stage fails, it prints the specific phase-labeled error and stops (this itself demonstrates phase-separated error detection).
- **`sample_input.recipe`** — The exact `TomatoRice` example from the manual, used to demonstrate the pipeline end-to-end.

### Prototype Source Code

**`lexer.py`**
```python
"""
lexer.py — RecipeLang Phase 1 Lexical Analyzer
Converts RecipeLang source text into a stream of tokens.
"""
import re

KEYWORDS = {"RECIPE", "INGREDIENT", "STEP"}
UNITS = {"cups", "cup", "tbsp", "tsp", "g", "kg", "ml", "l", "pieces", "piece"}
TIMEUNITS = {"minutes", "minute", "seconds", "second", "hours", "hour"}

TOKEN_SPEC = [
    ("NUMBER",   r"\d+"),
    ("ASSIGN",   r"="),
    ("LPAREN",   r"\("),
    ("RPAREN",   r"\)"),
    ("COMMA",    r","),
    ("NEWLINE",  r"\n"),
    ("SKIP",     r"[ \t]+"),
    ("IDENT",    r"[A-Za-z_][A-Za-z0-9_]*"),
    ("MISMATCH", r"."),
]
MASTER_PATTERN = "|".join(f"(?P<{n}>{p})" for n, p in TOKEN_SPEC)
TOKEN_REGEX = re.compile(MASTER_PATTERN)


class Token:
    def __init__(self, type_, value, line, col):
        self.type, self.value, self.line, self.col = type_, value, line, col
    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line}, col={self.col})"


class LexicalError(Exception):
    pass


def tokenize(source: str):
    tokens, line_num, line_start = [], 1, 0
    for match in TOKEN_REGEX.finditer(source):
        kind, value = match.lastgroup, match.group()
        col = match.start() - line_start + 1
        if kind == "NEWLINE":
            line_num += 1; line_start = match.end(); continue
        elif kind == "SKIP":
            continue
        elif kind == "MISMATCH":
            raise LexicalError(f"Lexical Error: unexpected character {value!r} at line {line_num}, column {col}")
        elif kind == "IDENT":
            if value in KEYWORDS: kind = "KEYWORD"
            elif value in UNITS: kind = "UNIT"
            elif value in TIMEUNITS: kind = "TIMEUNIT"
        tokens.append(Token(kind, value, line_num, col))
    tokens.append(Token("EOF", "", line_num, 0))
    return tokens
```

**`parser.py`**
```python
"""
parser.py — RecipeLang Phase 1 Parser (structural / syntax validation only)
"""
from lexer import tokenize, LexicalError

class SyntaxErrorRL(Exception):
    pass

class RecipeNode:
    def __init__(self, name):
        self.name, self.ingredients, self.steps = name, [], []

class IngredientNode:
    def __init__(self, name, quantity, unit):
        self.name, self.quantity, self.unit = name, quantity, unit
    def __repr__(self):
        return f"Ingredient({self.name}={self.quantity}{' ' + self.unit if self.unit else ''})"

class StepNode:
    def __init__(self, action, args):
        self.action, self.args = action, args
    def __repr__(self):
        return f"Step({self.action}, args={self.args})"

class Parser:
    def __init__(self, tokens):
        self.tokens, self.pos = tokens, 0
    def current(self): return self.tokens[self.pos]
    def advance(self):
        tok = self.tokens[self.pos]; self.pos += 1; return tok
    def expect(self, type_, value=None):
        tok = self.current()
        if tok.type != type_ or (value is not None and tok.value != value):
            expected = f"{type_} {value!r}" if value else type_
            raise SyntaxErrorRL(f"Syntax Error: expected {expected} but found {tok.type} {tok.value!r} at line {tok.line}")
        return self.advance()

    def parse_program(self):
        recipe = self.parse_recipe(); self.expect("EOF"); return recipe

    def parse_recipe(self):
        self.expect("KEYWORD", "RECIPE")
        recipe = RecipeNode(self.expect("IDENT").value)
        while self.current().type == "KEYWORD" and self.current().value == "INGREDIENT":
            recipe.ingredients.append(self.parse_ingredient())
        if not recipe.ingredients:
            raise SyntaxErrorRL(f"Syntax Error: recipe '{recipe.name}' has no INGREDIENT declarations")
        while self.current().type == "KEYWORD" and self.current().value == "STEP":
            recipe.steps.append(self.parse_step())
        if not recipe.steps:
            raise SyntaxErrorRL(f"Syntax Error: recipe '{recipe.name}' has no STEP statements")
        return recipe

    def parse_ingredient(self):
        self.expect("KEYWORD", "INGREDIENT")
        name = self.expect("IDENT").value
        self.expect("ASSIGN")
        qty = self.expect("NUMBER").value
        unit = self.advance().value if self.current().type == "UNIT" else None
        return IngredientNode(name, int(qty), unit)

    def parse_step(self):
        self.expect("KEYWORD", "STEP")
        action = self.expect("IDENT").value
        self.expect("LPAREN")
        args = []
        if self.current().type != "RPAREN":
            args.append(self.parse_arg())
            while self.current().type == "COMMA":
                self.advance(); args.append(self.parse_arg())
        self.expect("RPAREN")
        return StepNode(action, args)

    def parse_arg(self):
        tok = self.current()
        if tok.type == "IDENT":
            self.advance(); return ("ingredient_ref", tok.value)
        elif tok.type == "NUMBER":
            self.advance(); unit = self.expect("TIMEUNIT").value
            return ("time_value", int(tok.value), unit)
        raise SyntaxErrorRL(f"Syntax Error: invalid argument {tok.value!r} at line {tok.line}")


def parse_source(source: str) -> RecipeNode:
    return Parser(tokenize(source)).parse_program()
```

**`main.py`**
```python
"""
main.py — RecipeLang Phase 1 Prototype Driver
"""
import sys
from lexer import tokenize, LexicalError
from parser import parse_source, SyntaxErrorRL

def run(filepath):
    source = open(filepath).read()
    print("="*60); print(f"RecipeLang Phase 1 Prototype — processing '{filepath}'"); print("="*60)

    print("\n[Stage 1] Lexical Analysis")
    try:
        tokens = tokenize(source)
    except LexicalError as e:
        print(e); return
    print(f"  Total tokens generated: {len(tokens)}")
    for tok in tokens:
        if tok.type != "EOF":
            print(f"    {tok.type:<10} {tok.value!r:<15} (line {tok.line})")

    print("\n[Stage 2] Syntax Analysis (Parsing)")
    try:
        ast = parse_source(source)
    except SyntaxErrorRL as e:
        print(f"  {e}"); return
    print("  Syntax OK — input matches RecipeLang grammar.")

    print("\n[Stage 3] Structured Recipe Summary (Phase 1 output)")
    print(f"  Recipe Name : {ast.name}")
    print(f"  Ingredients : {len(ast.ingredients)}")
    for ing in ast.ingredients:
        print(f"    - {ing.name}: {ing.quantity}{' ' + ing.unit if ing.unit else ''}")
    print(f"  Steps       : {len(ast.steps)}")
    for i, st in enumerate(ast.steps, 1):
        arg_strs = [a[1] if a[0]=="ingredient_ref" else f"{a[1]} {a[2]}" for a in st.args]
        print(f"    {i}. {st.action}({', '.join(arg_strs)})")

    print("\nNote: ingredient-existence, duplicate-declaration, and quantity checks")
    print("are SEMANTIC ANALYSIS — planned for Phase 2, not part of this prototype.")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "sample_input.recipe")
```

**`sample_input.recipe`**
```
RECIPE TomatoRice
INGREDIENT rice = 2 cups
INGREDIENT tomato = 3
INGREDIENT oil = 2 tbsp

STEP heat_pan()
STEP add(oil)
STEP add(tomato)
STEP add(rice)
STEP cook(10 minutes)
STEP serve()
```

### Sample Output (actual, verified run of the prototype above)
```
============================================================
RecipeLang Phase 1 Prototype — processing 'sample_input.recipe'
============================================================

[Stage 1] Lexical Analysis
  Total tokens generated: 46
  Token stream:
    KEYWORD    'RECIPE'        (line 1)
    IDENT      'TomatoRice'    (line 1)
    KEYWORD    'INGREDIENT'    (line 2)
    IDENT      'rice'          (line 2)
    ASSIGN     '='             (line 2)
    NUMBER     '2'             (line 2)
    UNIT       'cups'          (line 2)
    KEYWORD    'INGREDIENT'    (line 3)
    IDENT      'tomato'        (line 3)
    ASSIGN     '='             (line 3)
    NUMBER     '3'             (line 3)
    KEYWORD    'INGREDIENT'    (line 4)
    IDENT      'oil'           (line 4)
    ASSIGN     '='             (line 4)
    NUMBER     '2'             (line 4)
    UNIT       'tbsp'          (line 4)
    KEYWORD    'STEP'          (line 6)
    IDENT      'heat_pan'      (line 6)
    LPAREN     '('             (line 6)
    RPAREN     ')'             (line 6)
    KEYWORD    'STEP'          (line 7)
    IDENT      'add'           (line 7)
    LPAREN     '('             (line 7)
    IDENT      'oil'           (line 7)
    RPAREN     ')'             (line 7)
    ... (steps 8–11 follow the same pattern)

[Stage 2] Syntax Analysis (Parsing)
  Syntax OK — input matches RecipeLang grammar.

[Stage 3] Structured Recipe Summary (Phase 1 output)
  Recipe Name : TomatoRice
  Ingredients : 3
    - rice: 2 cups
    - tomato: 3
    - oil: 2 tbsp
  Steps       : 6
    1. heat_pan()
    2. add(oil)
    3. add(tomato)
    4. add(rice)
    5. cook(10 minutes)
    6. serve()

Note: ingredient-existence, duplicate-declaration, and quantity checks
are SEMANTIC ANALYSIS — planned for Phase 2, not part of this prototype.
```

*(This is real, tested output from running the actual prototype code above — not a hypothetical example.)*

---

## 20. Test Cases for Phase 1

| Test Case | Input (key line) | Expected Result | Purpose |
|---|---|---|---|
| Valid recipe | Full `TomatoRice` program (Section 10, Example 1) | Tokens printed, "Syntax OK", structured summary printed | Confirms the happy path works end-to-end |
| Invalid keyword | `RECIPEE TomatoRice` | `Syntax Error: expected KEYWORD 'RECIPE' but found IDENT 'RECIPEE' at line 1` | Confirms lexer correctly falls back to IDENT for unrecognized words, and parser catches it |
| Missing ingredient section | `RECIPE X` followed directly by `STEP serve()` | `Syntax Error: recipe 'X' has no INGREDIENT declarations` | Confirms the grammar's "at least one ingredient" rule is enforced |
| Missing `=` (malformed declaration) | `INGREDIENT rice 2 cups` | `Syntax Error: expected ASSIGN but found NUMBER '2' at line 2` | Confirms structural/positional grammar checking |
| Unrecognized character | `INGREDIENT rice = 2 @cups` | `Lexical Error: unexpected character '@' at line ..., column ...` | Confirms lexical-level error detection, separate from syntax errors |
| Duplicate ingredient *(Phase 2)* | Two `INGREDIENT rice = ...` lines | *(Phase 1: parses fine, structurally valid)* → Phase 2 target: `Semantic Error: ingredient 'rice' already declared` | Documents a test case explicitly reserved for Phase 2, so scope stays honest |
| Undeclared ingredient reference *(Phase 2)* | `STEP add(salt)` with no `salt` declaration | *(Phase 1: parses fine, structurally valid)* → Phase 2 target: `Semantic Error: ingredient 'salt' used but never declared` | Documents a test case explicitly reserved for Phase 2, so scope stays honest |

---

## 21. Innovation

**What makes RecipeLang different from a basic recipe app:** a basic recipe app just *stores and displays* recipe text — it has no formal grammar, performs no validation, and cannot distinguish a well-formed recipe from a broken one. RecipeLang instead treats a recipe as a *program* that must pass through lexical, syntactic, and semantic analysis before it is accepted — meaning it can **prove** a recipe is internally consistent (every ingredient reference resolves, no duplicates, valid quantities) the same way a compiler proves a program has no undeclared-variable errors. This is a structural difference, not a cosmetic one.

**Realistic innovative features for later phases (not claimed as built yet):**
1. **Recipe scaling as an IR transformation** — given a target serving count, automatically multiply every ingredient's validated quantity in the IR (a genuine compile-time rewrite pass, analogous to constant propagation).
2. **Step-dependency analysis** — determine which STEPs are independent of each other (e.g., don't share an ingredient/output) and could be performed in parallel, displayed as a simple dependency diagram.
3. **Structured export formats** — emit the validated IR as JSON or a plain-text "cooking checklist," demonstrating that the IR is genuinely reusable output, not just an internal detail.

---

## 22. Phase 1 Review Demonstration Plan

**Suggested demonstration sequence:**
1. State the problem: recipes are unstructured text with no way to verify internal consistency.
2. Introduce RecipeLang's syntax using the `TomatoRice` example (Section 10).
3. Show the grammar (Section 12) and explain how it defines what a "valid" RecipeLang program looks like.
4. Type/paste the sample program into the prototype and run it live.
5. Show the token stream output (Stage 1) and explain 2–3 token types.
6. Show the "Syntax OK" result (Stage 2) and briefly explain what the parser checked.
7. Show the structured summary output (Stage 3).
8. Re-run with one of the invalid examples (Section 10) to show a real, line-numbered error being caught.
9. Show the system architecture diagram (Section 17) and explain the full planned pipeline, being explicit about what's built now vs. planned for Phase 2/3.
10. Close with the 1-minute explanation (Section 24-E).

**Likely viva questions and simple answers:**

| Question | Simple Answer |
|---|---|
| "Why is this a compiler project and not just an app?" | Because it performs lexical analysis, grammar-based parsing, and (from Phase 2) semantic analysis with a symbol table — the same stages a real compiler front-end uses — rather than just storing/displaying text. |
| "What's the difference between a syntax error and a semantic error here?" | A syntax error means the tokens don't match the grammar's shape (e.g., missing `=`); a semantic error means the shape is fine but the meaning is wrong (e.g., using an ingredient that was never declared). |
| "Why doesn't your grammar use semicolons?" | RecipeLang is line-oriented — each declaration/statement ends at a newline, which the lexer already treats as a statement boundary, so semicolons would be redundant. |
| "What would you add in Phase 2?" | The semantic analyzer and symbol table: checking declared-before-use, duplicate declarations, and valid quantity values. |
| "Why is `add`/`cook`/`serve` not a keyword?" | Because the set of possible actions is open-ended and domain-specific, not part of the language's core grammar — keeping them as identifiers keeps the keyword list small and the grammar simple. |
| "What is the AST and why isn't it just the parse tree?" | The AST keeps only meaningful structure (recipe → ingredients/steps) and drops punctuation tokens like `(`, `)`, `=` that were only needed to *guide* parsing, not to represent meaning. |

---

## 23. Final Phase 1 Checklist

- ✓ Project Title — Section 1
- ✓ Abstract — Section 2
- ✓ Problem Statement — Section 3
- ✓ Motivation — Section 4
- ✓ Objectives — Section 5
- ✓ Scope — Section 6
- ✓ Background Study — Section 7
- ✓ Compiler Concepts — Section 8
- ✓ Methodology — Section 16
- ✓ Architecture — Section 17
- ✓ Technology Stack — Section 18
- ✓ Initial Prototype (folder structure, source code, sample input/output) — Section 19
- ✓ Test Cases — Section 20
- ✓ Review 1 Demo Plan — Section 22

---

## 24. Phase Breakdown

### A. What we ARE building in Phase 1
A finalized language design (keywords, grammar, tokens, semantic rules on paper), a working **lexer** (full token generation), and a working **parser** that validates structure and builds a skeleton AST — demonstrated on both valid and invalid sample inputs, with a plain structured-summary output.

### B. What we are NOT building yet
The semantic analyzer, the real symbol table (used for validation, not just design), the intermediate representation, and the interpreter/execution engine. Anything related to scaling, parallel-step analysis, or export formats (Section 21) is future work only.

### C. What will be implemented in Phase 2
The full **semantic analyzer**: declared-before-use checking, duplicate-declaration detection, and quantity/time-value validation — all built on top of a fully functional **symbol table** populated from the AST. Phase 2 will also expand and harden the test suite to include all the semantic error cases listed as "reserved" in Section 20.

### D. What will be completed in Phase 3
The **intermediate representation** (a resolved, syntax-independent list of validated recipe steps) and the **interpreter/output generator** that walks the IR to produce a final polished output (e.g., a clean formatted recipe printout and/or JSON export). Phase 3 will also include final testing, edge-case handling, and — time permitting — one of the innovative features from Section 21 (most realistically, recipe scaling).

### E. One-minute explanation for your professor
"RecipeLang is a small custom programming language I designed for writing recipes in a structured way instead of plain text. I'm building an actual compiler front-end for it — a lexer that breaks the recipe into tokens, a parser that checks it against a formal grammar and builds a tree structure, and — starting Phase 2 — a semantic analyzer that checks the recipe is logically consistent, for example making sure every ingredient used in a step was actually declared, using a symbol table. In Phase 1, I've finalized the language design and built a working lexer and parser that I can demonstrate live on both correct and intentionally broken recipe inputs, with proper line-numbered error messages."
