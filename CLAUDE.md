# CLAUDE.md – HW1: Deterministic Search (Spider-Man Swings Through the City)

This file explains the assignment, the modeling decisions, the heuristic design, and the
step-by-step work plan. We execute the plan **one step at a time**, and the user approves each step before the next one starts.

---

## 0. Ground rules for working in this repo

- **Only `HW1_python/ex1.py` is submitted.** Do not modify `check.py`, `problems.py`, `search.py` or `utils.py`
  (the graders use their own copies). Helper or test scripts go in a separate file that is not submitted
  (for example `HW1_python/tests_local.py`), and they must not be imported by `ex1.py`.
- **Python 3.10, standard library only.** No numpy etc. (`math.lcm`, `heapq`, `itertools` are fine.)
- Names that must stay exactly as given: class `SpiderManProblem`, methods `actions`, `result`,
  `goal_test`, `h`, functions `create_spiderman_problem`, `astar_search`, list `ids`.
- `astar_search` must return a `search.Node` (check.py tests `isinstance(s, search.Node)` and
  reads the plan via `node.path()`), or `None` if there is no solution.
- Time limit: **60 s per problem, including the constructor** (all precomputation counts).
- The lecture/tutorial PDFs in `lectures and tutorials materials/` are password-protected, so this plan
  is based on the HW PDF and the handout code.
- Due: **3/12/2026 11:59**. Pairs. Fill both IDs (as strings) in `ids`.

---

## 1. The assignment in plain words

Spider-Man stands on a grid. He must reach the single destination tile `D` and then execute
`("finish",)`. We must return the **shortest plan in turns** (every action = 1 turn, finish included).
Web fluid is **not** what we minimize. It is a resource constraint that makes some plans illegal.

Grading:
| Part | Points | What it takes |
|---|---|---|
| Non-competitive | 85 | Optimal plan (min turns) on every problem like those in `non_comp_problems`, < 60 s each. Suboptimal = partial credit. Illegal plan = 0 for that problem. |
| Competitive | 25 | Optimal plans on **larger** hidden maps within 60 s. Ranked against other students and TA benchmarks. |

So we need two things: **(1) optimality** (admissible heuristic + correct A*), and
**(2) speed** (strong heuristic + small state space + efficient code).

---

## 2. Exact rules (the details that are easy to get wrong)

### 2.1 Order of events in one turn
1. Spider-Man chooses an action.
2. The action takes effect (swing cost, or refill). **If it is `finish`, the game ends here.**
3. All villains move one step.
4. Villain damage is applied, based on **end-of-turn** positions.

Legality: after (action cost + this turn's villain damage) the fluid must be **≥ 0**. Exactly 0 is legal.

### 2.2 Actions (all tuples; note the trailing commas)
| Action | Legal when | Fluid change |
|---|---|---|
| `("swing", (r, c))` | Same row or column, 1..`swing_range` tiles away. **Every tile on the way and the target** must be inside the map and not `I`. | `-k - max(0, h_dst - h_src) - dmg(dst)` |
| `("wait",)` | Always (if the damage still leaves fluid ≥ 0) | `-dmg(pos)` |
| `("refill",)` | On a cache whose cooldown is over | `min(max_fluid, f + amount) - dmg(pos)` (refill **before** damage) |
| `("finish",)` | On `D` | none (the villains never move after it) |

`dmg(x) = villain_damage × (number of villains standing on x after they moved)`.

Notes:
- Tiles you swing **over** have no effect (villains, caches, heights and D are ignored). Only the start
  and end tiles matter for height cost.
- Swapping tiles with a villain does not count as an encounter. Only the end-of-turn position counts.
- Two villains on the same tile mean damage × 2.
- No damage at time 0 (even if the start tile has a villain).
- The destination is never on a villain path.

### 2.3 Villains
A path `A, B, C, D` is walked back and forth: `A B C D C B A B …`.
- The cycle is `path + path[-2:0:-1]`, so the **period** is `2(L−1)` (or 1 if `L == 1`).
- After turn `t` the villain stands on `cycle[t % period]`.
- PDF example: path A,B,C, positions after turns 0,1,2,3,4,5 = A,B,C,B,A,B. ✓

### 2.4 Web caches
- Refill at turn `t` (turns are numbered from 1) means the cache is usable again at turn `t + cooldown + 1`.
- Refilling when already full is legal and still starts the cooldown.
- PDF example: cooldown 2, refill at turn 1 means blocked at turns 2 and 3, usable at turn 4. ✓
- Each cache has its own independent timer. No two caches share a tile.

### 2.5 Unsolvable problems
Some problems are impossible because of fluid. Then we must **return `None` within 60 s**, which means the search
must **terminate**. A finite state space + duplicate detection guarantees that. Strong pruning makes it
fast.

---

## 3. Modeling: the state

**Key question:** what is the minimum information such that the future depends only on it?

| Component | Why it is needed | Representation |
|---|---|---|
| Position | Obviously | Cell index `r * W + c` (an int is faster to hash than a tuple) |
| Fluid | Decides legality | int |
| Villain positions | Damage | **phase = t mod P**, `P = lcm(all villain periods)`. All villains are fully determined by the phase, so absolute time is not needed. |
| Cache availability | Refill legality | Tuple: per cache, the **remaining blocked turns** (0 = usable). This is relative, so it is time-independent. |
| Finished flag | The `finish` action must be a real step in the plan | Special state with `pos = -1` |

```
state = (pos, fluid, phase, cooldowns)      # all hashable built-ins
```

**Cooldown bookkeeping** (matches 2.4): refill is legal iff `cd[i] == 0`. In `result`, first decrement
every `cd` by 1 (floor 0), then set the refilled cache to `cooldown`.
Check: cd=2, refill at turn 1 gives rem=2. Turn 2 blocked, and after it rem=1. Turn 3 blocked, and after it rem=0.
Turn 4 usable. ✓

**Why the state space is finite:** pos ≤ H·W, fluid ≤ max(start, max_fluid), phase < P,
cooldowns bounded. So graph search with a closed set always terminates. This covers the unsolvable case.

**Static information** (stored on `self`, never in the state): the grid, heights, D, the precomputed swing
list per cell `[(dst, fluid_cost, action_tuple)]`, `dmg[phase] = {cell: damage}`, cache index by
cell, refill amounts, cooldowns, and the heuristic tables.

**Input quirks:** locations may be lists, so convert them to tuples. Actions must contain a **tuple** `(r, c)`.

---

## 4. Search: A*

The handout's `best_first_graph_search` is a stub, and `utils.PriorityQueue` is O(n) per operation.
We write our own A*:

- **`heapq`** min-heap with entries `(f, -g, counter, state, parent_node, action)`.
  - `-g` **tie-break toward deeper nodes**: among equal f, the one closer to the goal is expanded first.
    On grids this is a big speedup.
  - `counter` keeps the comparisons from reaching states or nodes.
- **Goal test when popping** (not when generating). This is required for optimality.
- **Lazy `Node` creation**: create a `search.Node` only when an entry is popped and accepted.
  Children are stored as (state, parent node, action), which saves time and memory on nodes that are never expanded.
- **Duplicate and dominance handling** (section 6): skip popped entries that became stale.
- Path cost = number of actions (default `Problem.path_cost`, +1 per step).
- If `h(start) = ∞`, return `None` immediately. Never push children with `h = ∞`.

Optimality argument: A* with an **admissible** h and a correct duplicate rule (a state is re-opened if a
strictly better g is found) returns an optimal solution. Our dominance rule only discards a
state when another state is provably at least as good (section 6).

---

## 5. The heuristic (the heart of the competitive part)

`h(node)` must **never overestimate** the remaining number of turns. Each layer below is a *relaxation*
of the real problem (we drop some rules), so its exact solution is a lower bound.

### H0 – trivial
`h = 0` if finished, else `1` (at least the finish). This is a correct baseline, used for cross-checking.

### H1 – swing-graph BFS distance (the "think about swing_range" hint)
**Relaxation:** ignore fluid, villains and caches. Keep walls and swing geometry.
Run a reverse BFS from D over the swing graph (edges are legal swings of 1..R tiles in a straight line
that do not pass through `I`). `d(p)` is the minimum number of swings from p to D.

`h1 = d(pos) + 1` (the +1 is the mandatory `finish`).

Why not Manhattan? `Manhattan / R` is admissible but weak. One swing changes only one
axis, and walls force detours. The exact BFS distance captures both and is still a lower bound.
Precomputed once: O(cells × 4 × R).

### H2 – fluid-aware distance (main upgrade)
**Relaxation:** ignore villains (they only *remove* fluid, so ignoring them is optimistic) and caches' timing.
Keep the real swing fluid costs (length + climb).

Precompute, for each cell p, the **Pareto breakpoints** `(F_k, k)`:
`F_k(p)` = minimum fluid needed to reach D in **at most k swings**. Then

`T(p, f) = min { k : F_k(p) ≤ f }`, the fewest swings to reach D with the fluid we have and no refill.

Computed by layered Bellman–Ford from D:
`F_0(D) = 0`, `F_{k+1}(p) = min(F_k(p), min over swings p→q of cost(p,q) + F_k(q))`.
Only cells whose value changed in layer k can improve their predecessors in layer k+1, so
we propagate a "changed" frontier only. This is fast even on 50×50. Values above the fluid cap are dropped.

**Refills.** If the current fluid is not enough, the plan must refill at some cache first. We compute the same
tables toward each cache c: `T_c(p, f)`. We also compute `G(c)`, a lower bound on turns from standing on cache
c to finishing, **including the refill turn**. It allows more refills later:

```
G(c) = 1 + min( T_D(c, cap),  min over c' ≠ c: T_{c'}(c, cap) + G(c') )     (fixed point over caches)
```
where `cap = max(max_web_fluid, starting_web_fluid)`, an upper bound on fluid after any refill.

**Final heuristic:**
```
h(pos, f) = 1 + min( T_D(pos, f),                       # never refill
                     min over caches c: T_c(pos, f) + G(c) )   # first refill happens at c
```
- **Admissible:** every real plan either never refills (its swings cost ≤ f, so it needs ≥ T_D swings),
  or has a *first* refill at some c (it reaches c without refilling, so it needs ≥ T_c swings, then it needs ≥ G(c)). Waits only add turns.
- **Dead-state detection:** if h = ∞, no plan exists from this state, so we prune it. This is what makes
  **unsolvable** problems terminate quickly, and it also cuts a lot of hopeless branches in solvable ones.
- Depends only on `(pos, fluid)`, so we **memoize** it in a dict.
- Always at least as large as H1 (with f = ∞ it reduces to H1), so it is at least as good.

### Possible later improvements (only if measurements show a need)
- Cooldown-aware G: a cache still cooling for r turns cannot be refilled before then.
- Villain-aware bounds for single stationary villains (permanent "costly" tiles).

---

## 6. Search-space reductions (all preserve optimality)

1. **Finish immediately on D.** Once on D, the only successor generated is `finish`. Any plan that
   leaves D and comes back is longer.
2. **Fluid dominance.** Two states with the same `(pos, phase, cooldowns)`: if A has
   `g_A ≤ g_B` and `fluid_A ≥ fluid_B`, then A dominates B. Every action sequence legal from B is legal from
   A (fluid legality is monotone, refill `min(max, f+a)` is monotone), and it reaches the goal no later. We keep a
   Pareto front of `(g, fluid)` per key, discard dominated states when they are generated, and skip stale heap
   entries when they are popped. This replaces the plain "closed set" and collapses the fluid dimension.
3. **Small P when possible:** no villains gives P = 1. Stationary villains (path length 1) contribute period 1.
4. **No caches:** the cooldowns tuple is `()`.
5. Waits are generated, but useless waits (no villains, nothing cooling) are removed automatically by
   dominance (same state, larger g).

---

## 7. Step-by-step execution plan

Each step ends with something we can run and check. We stop after each step for review.

- [ ] **Step 1 – Parsing and static tables (`__init__`).**
  Grid → passable/D/heights. Swing list per cell (stop scanning at the first `I` or the border). Villain
  cycles, `P`, `dmg[phase]`. Cache tables. Initial state. *Check:* print the tables for problem 12 and
  compare them by hand with the PDF (swing costs, the villain positions for the first turns).
- [ ] **Step 2 – `actions` / `result` / `goal_test`.**
  Implemented through one `successors(state)` helper that returns `[(action, next_state)]`, so the
  rules live in exactly one place. *Check:* step through the PDF examples (the 9 − 1 − 5 = 3 villain example, the
  refill-before-damage example, the cooldown example).
- [ ] **Step 3 – Independent validator (local, not submitted).**
  `tests_local.py`: replays a plan from the **raw input dict**, written directly from the PDF wording
  (absolute turn numbers, `t + cooldown + 1`). It deliberately does not reuse our model code, so it can catch
  modeling bugs.
- [ ] **Step 4 – A* with H0 (h = 1), then BFS-equivalent cross-check.**
  Run on all 12 non-comp problems. Validate every plan. Record the optimal lengths, which become the
  ground truth. Problem 2 must return `(-2, -2, None)`. Problem 1 must take 5 turns. Problem 3 must take 5 turns.
- [ ] **Step 5 – H1 (swing BFS).** The plan lengths must equal Step 4's. Measure the speedup.
- [ ] **Step 6 – H2 (fluid-aware, with caches and dead-state pruning).** Same lengths, and assert
  `h(root) ≤ optimal`. Measure.
- [ ] **Step 7 – Dominance pruning and performance tuning.** Lazy nodes, tie-breaking, h memoization.
- [ ] **Step 8 – Stress testing.** A random small-map generator (walls, heights, villains, caches,
  tight fluid). Compare A*+H2 against A*+H0 lengths on hundreds of instances, and validate every plan.
- [ ] **Step 9 – Competitive runs.** Uncomment `comp_problems` in a *local copy* of the checker, time
  C1–C4, profile (`cProfile`) and optimize hot spots. Also try bigger generated maps.
- [ ] **Step 10 – Final submission check.** `ids` filled. No debug prints. No imports beyond the stdlib and handout
  modules. Run `check.py` exactly as given.

---

## 8. Verification checklist (we are responsible for correctness)

- Every returned plan replays legally in the independent validator and ends with `("finish",)`.
- Optimal length = length found with `h = 0` on every test (small instances).
- `h(initial) ≤ optimal length` asserted on all tests (admissibility smoke test).
- Unsolvable instances return `None` well under 60 s.
- All actions are tuples, and swing targets are `(r, c)` tuples.

## 9. Commands

```
cd HW1_python
python check.py              # official runner (non-comp problems)
python tests_local.py        # our validator + cross-checks (local only)
```
