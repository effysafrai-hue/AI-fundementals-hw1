# CLAUDE.md – HW1: Deterministic Search (Spider-Man Swings Through the City)

This file describes the assignment, the modeling decisions we made TOGETHER, and the staged
work plan. It replaces the earlier version of this file.

---

## 0. How we work (read this first)

The user is a student who wants to understand every decision, not just receive code.
Therefore:

1. **One step at a time.** Never start the next step before the user confirms the current one
   passed its tests.
2. **Explain before coding.** Before writing code for a step, state: what the step does, why it is
   needed, and which alternatives exist (if there is a real choice). Keep it short and concrete.
3. **Decisions belong to the user.** When a step contains a real design choice, present the options
   with their trade-off and ask. Record the outcome in section 3 ("Decisions made").
4. **Write small pieces.** Prefer one function or table per message so the user can read and run it.
5. **The user runs the tests.** Provide the test command and the expected result. Do not claim
   something works unless it was run.
6. **Link to the course.** The course material is in `lectures and tutorials materials/`
   (tutorial 1: modeling a problem as search / transition system, tutorial 2: Problem/Node/search code and A*,
   lectures ai01, ai03, ai04). Connect explanations to those concepts: state, successor function,
   goal test, g/h/f, admissibility, relaxation.
7. The user reads Hebrew. Explanations may be in Hebrew; **code, identifiers and formulas stay in
   English** and are never mixed inline inside Hebrew sentences (put them on separate lines or in code blocks).

---

## 1. Ground rules for the repo

- **Only `HW1_python/ex1.py` is submitted.** Do not modify `check.py`, `problems.py`, `search.py`, `utils.py`
  (the graders use their own copies). Helper and test scripts live in a separate file that is not
  submitted (e.g. `HW1_python/tests_local.py`) and must never be imported by `ex1.py`.
- **Python 3.10, standard library only** (`math.lcm`, `heapq`, `itertools` are fine).
- Names that must stay exactly as given: class `SpiderManProblem`; methods `actions`, `result`,
  `goal_test`, `h`; functions `create_spiderman_problem`, `astar_search`; list `ids`.
- `astar_search` returns a `search.Node` (check.py tests `isinstance(s, search.Node)` and reads the plan
  via `node.path()`), or `None` when there is no solution.
- **60 s per problem, constructor included** (all precomputation counts).
- `search.best_first_graph_search` is an empty stub, and `utils.PriorityQueue` is slow, so we write our own A*.
- Due: **3/12/2026 11:59**. Pairs. Fill both IDs (as strings) in `ids`.

---

## 2. The assignment in plain words

Spider-Man stands on a grid. He must reach the single destination tile `D` and then execute
`("finish",)`. We return the **shortest plan in turns** (every action is 1 turn, finish included).
Web fluid is NOT minimized. It is a resource constraint that makes some plans illegal.

| Part | Points | What it takes |
|---|---|---|
| Non-competitive | 85 | Optimal plan on every problem like `non_comp_problems`, < 60 s each. Suboptimal = partial credit. Illegal plan = 0 for that problem. |
| Competitive | 25 | Optimal plans on larger hidden maps within 60 s, ranked against other students and TA solutions. |

Stages A and B (below) target the 85 points. Stage C targets the competitive part.

### 2.1 Order of events in one turn
1. Spider-Man chooses an action.
2. The action takes effect (swing cost, or refill). If it is `finish`, the game ends here.
3. All villains move one step.
4. Villain damage is applied, based on end-of-turn positions.

Legality: after (action cost + this turn's villain damage) the fluid must be >= 0. Exactly 0 is legal.

### 2.2 Actions (all tuples, note the trailing commas)
| Action | Legal when | Fluid change |
|---|---|---|
| `("swing", (r, c))` | Same row or column, 1..`swing_range` tiles away. Every tile on the way AND the target is inside the map and not `I`. | `-k - max(0, h_dst - h_src) - dmg(dst)` |
| `("wait",)` | Always, if the damage still leaves fluid >= 0 | `-dmg(pos)` |
| `("refill",)` | On a cache whose cooldown is over | `min(max_fluid, f + amount) - dmg(pos)` (refill BEFORE damage) |
| `("finish",)` | On `D` | none |

`dmg(x) = villain_damage * (number of villains on x after they moved)`.

Notes:
- Tiles swung OVER have no effect (villains, caches, heights, D). Only start and end tiles matter for height cost.
- Swapping tiles with a villain is not an encounter. Only end-of-turn positions count.
- Two villains on one tile means damage x 2.
- No damage at time 0, even if the start tile holds a villain.
- The destination is never on a villain path.

### 2.3 Villains
A path `A, B, C, D` is walked back and forth: `A B C D C B A B ...`
- Cycle = `path + path[-2:0:-1]`, so period = `2 * (L - 1)` (period 1 if `L == 1`).
- After turn `t` the villain stands on `cycle[t % period]`.
- PDF example: path A,B,C gives A,B,C,B,A,B after turns 0..5.

### 2.4 Web caches
- Refill at turn `t` (turns numbered from 1) means usable again at turn `t + cooldown + 1`.
- Refilling when full is legal and still starts the cooldown.
- PDF example: cooldown 2, refill at turn 1 means blocked at turns 2 and 3, usable at turn 4.
- Each cache has an independent timer. No two caches share a tile.

### 2.5 Unsolvable problems
Some problems are impossible because of fluid. The search must then terminate and return `None`
within 60 s. A finite state space with duplicate detection guarantees termination.

---

## 3. Decisions made (the user took part in each)

| # | Decision | Choice | Reason |
|---|---|---|---|
| D1 | What is in the state | `(pos, fluid, phase, cooldowns)` | The minimum the future depends on. Static data stays on `self`. |
| D2 | Time / villains | `phase = t mod P`, with `P = lcm` of ALL villain periods | Keeps the state space finite (needed to terminate on unsolvable problems). |
| D3 | Position | Single int `r * W + c` | Faster to hash than a tuple. Convert at input and output only. |
| D4 | "Finished" | Special `pos = -1` | One int, no extra state component. |
| D5 | Order of heuristics | Build a correct baseline first (h trivial, then swing-graph BFS), advanced heuristics only afterwards | Gives a ground truth to compare against. |
| D6 | A* tie-break among equal f | Larger g first: heap entry `(f, -g, counter, node)` | Reaches a goal faster inside the last f-layer; never changes optimality. Can be upgraded to `(-g, -fluid)` later if measured to help. |

**Important correction on D2:** P must be the **LCM** of all villain periods, NOT the longest period.
The longest period is only correct if every other period divides it. Example: periods 4 and 6 with modulus 6 would
treat t=0 and t=6 as the same phase, but the period-4 villain is on a different tile in each. Use 12.
Also note that a villain's full cycle is `2*(L-1)` (there and back), not `L`.
P can grow quickly (periods 6, 8, 10, 14 give 840). Watch it when measuring performance.

**Pitfall on D4:** in Python, index `-1` does not raise, it silently reads the LAST element. Every table lookup by `pos`
must handle the finished state first.

Open decisions (decide with the user when we reach them): see the "Decision point" lines in section 5.

---

## 4. The state, in detail

```
state = (pos, fluid, phase, cooldowns)      # all hashable built-ins
```

| Component | Why it is needed | Representation |
|---|---|---|
| pos | Where Spider-Man is | int, `-1` means finished |
| fluid | Decides legality | int |
| phase | Villain positions (and thus damage) | `t mod P` |
| cooldowns | Refill legality | tuple, per cache the remaining blocked turns (0 = usable) |

Cooldown bookkeeping: refill is legal iff `cd[i] == 0`. In `result`, first decrement every `cd` by 1 (floor 0), then set the
refilled cache to its `cooldown`. Check: cd=2 after a refill at turn 1; after turn 2 it is 1; after turn 3 it is 0; turn 4 is usable.

Why the state space is finite: pos <= H*W, fluid <= max(start, max_fluid), phase < P, cooldowns bounded.

Static data (on `self`, never in the state): grid, heights, D, swing list per cell `[(dst, fluid_cost, action_tuple)]`,
`dmg[phase][cell]`, cache index by cell, refill amounts, cooldown lengths, heuristic tables.

Input quirks: locations may be lists, so convert to tuples. Action targets must be **tuples** `(r, c)`.

---

## 5. The plan (stages and gates)

**Gate rule:** a step is finished only when its test passes and the user confirms. Do not start the next step before that.

### Stage A: the model (the rules of the game)

- [ ] **Step 1 – Constructor and static tables.**
  Convert input; build walls/heights; per-cell swing list (stop scanning at the first `I` or the border); villain cycles, `P`,
  `dmg[phase]`; cache tables; initial state.
  *Test:* print the tables for the PDF example and compare by hand: swing cost 3 tiles from height 1 to 4 equals 6; path A,B,C gives
  A,B,C,B,A,B.
  *Decision point:* none new (D1..D4 are fixed).

- [ ] **Step 2 – `actions` / `result` / `goal_test`.**
  Implement ONE shared helper that returns `[(action, next_state)]`, and derive the three required functions from it,
  so the rules live in exactly one place. On `D`, the only action generated is `finish`.
  *Test:* the three numeric examples of the PDF: 9 - 1 - 5 = 3 (villain), refill before damage (2 + 4 - 3 = 3),
  cooldown 2 usable at turn 4.

- [ ] **Step 3 – Independent validator (local, not submitted).**
  `tests_local.py` replays a plan from the RAW input dict, written directly from the PDF wording (absolute turn numbers,
  `t + cooldown + 1`). It must NOT reuse model code, so that it can catch modeling bugs. The graders replay every plan, and an
  illegal plan scores 0.

### Stage B: the engine (this stage covers the 85 points)

- [ ] **Step 4 – A* with a trivial heuristic.**
  Own `heapq` A*. Goal test when POPPING (not when generating). Keep best g per state and re-open a state if a better g is found.
  Return the goal `Node` (so `path()` works) or `None` when the heap empties. If `h(start)` is infinite, return `None`.
  `h = 0` if finished, else `1`.
  *Test:* run all 12 non-comp problems, validate every plan, record the optimal lengths as GROUND TRUTH.
  Known: problem 1 = 5 turns, problem 3 = 5 turns, problem 2 returns `(-2, -2, None)`.
  *Decision point:* how to break ties among equal f (e.g. prefer larger g).

- [ ] **Step 5 – Heuristic H1: swing-graph BFS.**
  Reverse BFS from `D` over the swing graph (edges = legal swings of 1..R tiles in a straight line that do not cross `I`).
  `h = d(pos) + 1` (the +1 is the mandatory finish). Computed once in the constructor, then looked up.
  Why not Manhattan / R: it is admissible but weak (one swing changes one axis only, walls force detours).
  *Test:* lengths must be IDENTICAL to Step 4. Only time may drop. Also assert `h(root) <= optimal`.

### Stage C: improvements (only after Stage B is correct; mainly for the competitive 25 points)

- [ ] **Step 6 – Fluid-aware heuristic H2 with dead-state pruning.**
  Relaxation: ignore villains (they only remove fluid) and cache timing; keep real swing costs.
  For each cell compute Pareto breakpoints `(F_k, k)` = minimum fluid to reach `D` in at most k swings (layered Bellman-Ford from `D`).
  `T(p, f) = min { k : F_k(p) <= f }`.
  Refills: tables toward each cache `c`, and `G(c)` = lower bound on turns from standing on `c` to finishing, refill turn included,
  `cap = max(max_web_fluid, starting_web_fluid)`:
  ```
  G(c) = 1 + min( T_D(c, cap),  min over c' != c: T_c'(c, cap) + G(c') )
  h(pos, f) = 1 + min( T_D(pos, f),  min over caches c: T_c(pos, f) + G(c) )
  ```
  Admissible: a real plan either never refills (needs >= T_D swings) or has a first refill at some `c`. `h = infinity` means
  no plan exists from this state, so the state is pruned (this also makes unsolvable problems finish quickly). Memoize on `(pos, fluid)`.
  Further ideas only if measurement shows a need: cooldown-aware `G`, villain-aware bounds.
  *Test:* same lengths as Step 4, `h(root) <= optimal`, and a measured speed-up.
  *Decision point:* whether to do it at all (depends on how Step 5 performs).

- [ ] **Step 7 – Dominance pruning and speed tuning.**
  Same `(pos, phase, cooldowns)`: if A has `g_A <= g_B` and `fluid_A >= fluid_B`, then A dominates B (any plan legal from B is legal from A and
  no later). Keep a Pareto front of `(g, fluid)` per key, drop dominated states on generation, skip stale heap entries on pop.
  Other speed-ups: lazy `Node` creation (create the Node only when an entry is popped), memoized `h`.
  These change speed, never the result.

- [ ] **Step 8 – Stress tests.**
  Random small-map generator (walls, heights, villains, caches, tight fluid). Compare plan lengths against the Step 4 baseline on hundreds
  of instances and validate every plan.

- [ ] **Step 9 – Competitive runs.**
  Run `comp_problems` in a local copy of the checker, time them, profile with `cProfile`, fix measured hot spots.

### Stage D: submission

- [ ] **Step 10 – Final check.**
  `ids` filled with strings, no debug prints, only stdlib imports, run `check.py` exactly as given.

---

## 6. Heuristic principles (for explanations)

- A heuristic is a **relaxation**: drop some rules, solve the easier problem exactly, and use the answer as a lower bound.
  Fewer dropped rules means a stronger but costlier heuristic.
- **Admissible** means it never overestimates the true remaining turns. This is what makes A* return an optimal plan. An inadmissible
  heuristic can cost points (non-optimal plans); a weak one only costs time.
- Combining heuristics: the **max** of admissible heuristics is admissible; do NOT sum them unless they measure independent things.
- Trade-off: total time is roughly (nodes expanded) x (cost per node). A stronger heuristic lowers the first factor and raises the second.
  Measure before deciding.
- Generated vs expanded: all legal swings of 1..R in 4 directions are generated, but only the lowest-f nodes are expanded.
  Do not restrict actions to "the longest swing".

---

## 7. Verification checklist

- Every returned plan replays legally in the independent validator and ends with `("finish",)`.
- The optimal length equals the length found by the trivial-heuristic baseline on every test.
- `h(initial) <= optimal length` on all tests.
- Unsolvable instances return `None` well under 60 s.
- All actions are tuples; swing targets are `(r, c)` tuples.

## 8. Commands

```
cd HW1_python
python check.py              # official runner (non-comp problems)
python tests_local.py        # our validator and cross-checks (local only)
```
