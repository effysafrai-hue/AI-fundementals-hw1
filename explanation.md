# HW1 – Explanations, step by step

---

## Step 3 – Independent validator (local only, not submitted)

### What it is
`HW1_python/tests_local.py` contains a small simulator, `Sim`, and a function

```python
validate(game, plan) -> (ok, message)
```

that replays a plan on the **raw input dict** turn by turn and says whether it is legal.
It is never imported by `ex1.py` and is not submitted.

### Why we need it
1. **The graders replay every plan.** An illegal plan scores 0 for that problem, even if it is short.
   Being optimal is worthless if the plan breaks a rule.
2. **A search algorithm trusts its model blindly.** A* finds the optimal path *in the transition system
   we built* (tutorial 1: states + successor function + goal test). If the successor function has a bug
   (wrong damage turn, off-by-one cooldown), A* will happily return an "optimal" plan for the wrong game.
   Testing A* against itself can never reveal that. We need a second, independent opinion.
3. **Ground truth for later steps.** From Step 4 on, every plan A* returns is passed through `validate`.

### Why it must be *independent*
If the validator reused `ex1`'s tables, a bug in those tables would appear in both and the two would agree
on the wrong answer. So the validator is written directly from the PDF wording, with a deliberately
**different representation** for every rule:

| Rule | `ex1` (the model) | Validator |
|---|---|---|
| Position | int `r * W + c` | tuple `(r, c)` |
| Time | `phase = t mod P` | absolute turn number `t` |
| Villain position | precomputed cycle list `path + path[-2:0:-1]` | `villain_at(path, t)`: index bounced back and forth |
| Damage | sparse dict `dmg[phase]` | counts villains on the tile after turn `t` |
| Cooldown | counter per cache, decremented each turn | stores the turn of the last refill; legal iff `turn >= last + cooldown + 1` (PDF wording) |
| Swing legality | precomputed swing list per cell | walks tile by tile at replay time |

The turn order follows the PDF exactly:

```
1. read the action
2. apply it (swing cost / refill with cap)      -> if finish: game ends, no damage
3. villains move  (positions at turn t)
4. damage from end-of-turn position; fluid must be >= 0
```

The validator is also **stricter about format** than the model needs to be: actions must be tuples,
swing targets must be `(r, c)` tuples (not lists), and no action may follow `("finish",)`.

### How it is tested (two parts)

**Part A – the validator tests itself** (`test_step3_validator`):
hand-made plans with a known answer.
- Legal: problem 1, `swing x4 + finish`, ends with fluid 6.
- Illegal: diagonal swing, swing longer than `R`, swing off the map, swing over `I`, finish not on `D`,
  no finish at the end, action after finish, list instead of tuple.
- The PDF numbers: `9 - 1 - 5 = 3`, `2 + 4 - 3 = 3`, cooldown 2 (blocked at turns 2 and 3, usable at 4),
  fluid exactly 0 legal, the villain walk `A B C B A B`.

**Part B – cross-check model vs validator** (`test_step3_crosscheck`):
for each of the 12 `non_comp_problems`, 100 random walks of up to 30 turns through the **model**.
At every visited state, *every candidate action* (wait, refill, finish, swings of length 1..R+1 in
all 4 directions, including illegal ones) is tried in both:

```
legal in ex1   <=>   legal in validator
and, when legal: same position and same fluid afterwards
```

This compares thousands of transitions, including the illegal ones, which hand tests rarely cover.
Refills are chosen with a 30% bias so that cooldowns are actually exercised.
The seed is fixed (`12345`) so a failure is reproducible.

### One intended difference: standing on `D`
On `D` the model generates **only** `("finish",)`, while the real game also allows waiting or swinging there.
This is a safe pruning, not a bug: if you are on `D` at turn `t`, finishing now gives a plan of length `t + 1`,
and any plan that leaves or waits finishes later. So no optimal plan ever does anything other than finish on `D`.
The cross-check skips the non-finish actions on `D` and only asserts that the model indeed does not generate them.

### Run

```
cd HW1_python
py tests_local.py
```

Expected: the Step 1 and Step 2 lines, then

```
step 3 (validator self-test): all checks passed
  problem  1:  ... comparisons, no mismatch
  ...
  problem 12:  ... comparisons, no mismatch
step 3 (cross-check model vs validator): ... comparisons, all agree
```

If a `MISMATCH` assertion fires, it prints the action, what each side said, the model state and the turn,
which is enough to find which of the two misreads the rules (then we re-read the PDF to decide).

---

## Step 4 – A* with a trivial heuristic (the baseline)

### What it is
Two pieces of code in `ex1.py`:

1. `h(node)` – the simplest admissible heuristic:
   ```
   h = 0   if the state is finished (pos == -1)
   h = 1   otherwise
   ```
2. `astar_search(problem, heuristic)` – our own A* with `heapq`
   (the course's `best_first_graph_search` is an empty stub and `utils.PriorityQueue` is slow).

### Why start with a trivial heuristic
A* is **optimal whenever h is admissible** (lecture ai03/ai04: h never overestimates the true remaining cost).
`h = 1` is obviously admissible: any unfinished state still needs at least the `finish` turn.
With such a weak h, A* behaves almost like uniform-cost search (= BFS here, since every action costs 1),
so it is slow but **certainly correct**. Its plan lengths become our **ground truth**: every stronger heuristic
later (Step 5, 6) must produce exactly the same lengths. If it doesn't, the new heuristic is inadmissible.

It is also consistent: for every edge `s -> s'`, `h(s) <= 1 + h(s')` (1 <= 1 + 0 or 1 <= 1 + 1).

### The algorithm (tutorial 2, adapted)

```
g(root) = 0, f = g + h
push root
best_g = {root.state: 0}
loop:
    pop the node with the smallest f (ties: see decision below)
    if node.g > best_g[node.state]:   skip            # stale entry, a better path was found later
    if goal_test(node.state):         return node     # goal test on POP, not on generation
    for (action, s2) in successors(node.state):
        g2 = node.g + 1
        if g2 < best_g.get(s2, inf):
            best_g[s2] = g2
            push Node(s2, node, action, g2) with f = g2 + h
heap empty -> return None                             # no solution
```

Key points and why:

| Point | Why |
|---|---|
| **Goal test when popping**, not when generating | A goal generated now may have a larger g than another goal reachable later. Only when it is popped with the smallest f is it guaranteed optimal (lecture: A* optimality proof). |
| **`best_g` per state** (graph search, duplicate detection) | Same state reached by many paths (e.g. wait-wait vs. swing-back-and-forth). Without it the search explodes and, on unsolvable problems, never terminates. Our state space is finite (D2), so with duplicate detection the heap must eventually empty -> `None`. |
| **Re-open if a better g is found** | Required for correctness with a non-consistent heuristic. Our h is consistent, so it never actually happens now, but later heuristics might not be; this keeps the engine safe for them. |
| **Skip stale entries on pop** | `heapq` has no "decrease key". Instead we push a new entry and ignore the old one when it comes out. |
| **Use `problem._successors` directly** | One call gives both action and next state. `actions` + `result` would compute every successor twice. |
| **Return a `search.Node`** | `check.py` checks `isinstance(s, search.Node)` and reads the plan with `node.path()`. |
| **`h(root) == inf` -> return `None`** | Not relevant for `h = 1`, but Step 6 uses `inf` to mean "provably unsolvable". |

### Heap entry and the counter
Python compares tuples element by element. If two entries had equal f and equal tie-break value,
Python would then compare the `Node`s themselves (`Node.__lt__` compares states – works, but slow and meaningless).
So each entry gets a unique increasing **counter** before the node:
```
(f, tie_break_key, counter, node)
```

### Decision point: tie-breaking among equal f
Many nodes have the same f. Which one to pop first does **not** affect optimality
(any order among equal-f nodes still returns an optimal plan) but it affects **how many nodes are expanded**.

| Option | Key | Effect |
|---|---|---|
| **A. Prefer larger g** (deeper first) | `-g` | Among equal f, the node closer to the goal (by h) is preferred. Typically reaches a goal with f = optimum quickly instead of expanding the whole f-layer. Standard choice. |
| B. FIFO (older first) | only the counter | Simplest. Expands most of the last f-layer before the goal. |
| C. Larger g, then more fluid | `(-g, -fluid)` | Like A, plus prefers states with more web fluid, which are more likely to be able to finish. Small extra cost per push. |

With `h = 1` the difference is small (f = g + 1 almost everywhere). It starts to matter with the BFS heuristic (Step 5).
Recommendation: **A**, possibly upgraded to C later if measurements show it helps (it does not change results).

### What we measure (the test)
`test_step4` in `tests_local.py` runs every `non_comp_problem`:
- the plan length, time and number of expanded nodes,
- every plan through `validate` (Step 3) – must be legal and end with `("finish",)`,
- known values: problem 1 = 5 turns, problem 2 = no solution, problem 3 = 5 turns.

The printed lengths become the **ground-truth table** for Steps 5–8.
