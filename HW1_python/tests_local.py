"""Local tests only. NOT submitted, never imported by ex1.py."""
import random
import ex1
from problems import non_comp_problems


# =============================================================================
# Step 3: independent validator.
# Written from the PDF wording, on the RAW input dict. It must NOT use any
# table or helper from ex1 (absolute turn numbers, (r, c) tuples, no phases,
# no cooldown counters), so that a modeling bug in ex1 shows up as a mismatch.
# =============================================================================

class _Static:
    """The raw game, unpacked once (shared by all copies of a Sim)."""

    def __init__(self, game):
        self.grid = game["map"]
        self.heights = game["heights"]
        self.H, self.W = len(self.grid), len(self.grid[0])
        sm = game["spiderman"]
        self.start = tuple(sm["starting_location"])
        self.start_fluid = sm["starting_web_fluid"]
        self.max_fluid = sm["max_web_fluid"]
        self.R = sm["swing_range"]
        self.vdmg = sm["villain_damage"]
        self.villains = [[tuple(p) for p in path] for path in game["villains"].values()]
        self.caches = [(tuple(c["location"]), c["refill_amount"], c["cooldown"])
                       for c in game["web_caches"]]


def villain_at(path, t):
    """Where a villain stands after turn t (t = 0 is the start).
    Back and forth by bouncing an index -- deliberately NOT the cycle list of ex1."""
    L = len(path)
    if L == 1:
        return path[0]
    m = t % (2 * (L - 1))
    return path[m] if m < L else path[2 * (L - 1) - m]


class Sim:
    """Plays the game turn by turn, exactly as the PDF describes it."""

    def __init__(self, game=None, _static=None):
        self.s = _static or _Static(game)
        self.t = 0                       # number of turns played so far
        self.pos = self.s.start          # (r, c)
        self.fluid = self.s.start_fluid
        self.finished = False
        self.last_refill = {}            # cache index -> turn number of its last refill

    def clone(self):
        c = Sim(_static=self.s)
        c.t, c.pos, c.fluid, c.finished = self.t, self.pos, self.fluid, self.finished
        c.last_refill = dict(self.last_refill)
        return c

    def step(self, action):
        """Play one turn. Returns None if legal, else a string saying why not.
        After an illegal step the Sim is in an undefined state (use a clone)."""
        s = self.s
        if self.finished:
            return "action after finish"
        if not isinstance(action, tuple) or len(action) == 0:
            return "action %r is not a non-empty tuple" % (action,)
        turn = self.t + 1
        r, c = self.pos
        kind = action[0]

        # 1-2. the action takes effect
        if kind == "swing":
            if len(action) != 2 or not isinstance(action[1], tuple) or len(action[1]) != 2:
                return "bad swing format %r" % (action,)
            tr, tc = action[1]
            if tr != r and tc != c:
                return "swing is not along a row or a column"
            k = abs(tr - r) + abs(tc - c)
            if not 1 <= k <= s.R:
                return "swing distance %d not in 1..%d" % (k, s.R)
            dr = (tr > r) - (tr < r)
            dc = (tc > c) - (tc < c)
            for i in range(1, k + 1):        # every tile on the way AND the target
                rr, cc = r + dr * i, c + dc * i
                if not (0 <= rr < s.H and 0 <= cc < s.W):
                    return "swing leaves the map"
                if s.grid[rr][cc] == 'I':
                    return "swing crosses or lands on I at %r" % ((rr, cc),)
            self.fluid -= k + max(0, s.heights[tr][tc] - s.heights[r][c])
            self.pos = (tr, tc)
        elif kind == "wait":
            if len(action) != 1:
                return "bad wait format"
        elif kind == "refill":
            if len(action) != 1:
                return "bad refill format"
            idx = [i for i, (loc, _, _) in enumerate(s.caches) if loc == self.pos]
            if not idx:
                return "refill not on a cache"
            i = idx[0]
            _, amount, cooldown = s.caches[i]
            # refill at turn t -> usable again at turn t + cooldown + 1
            if i in self.last_refill and turn < self.last_refill[i] + cooldown + 1:
                return "cache still cooling down (turn %d)" % turn
            self.fluid = min(s.max_fluid, self.fluid + amount)   # refill BEFORE damage
            self.last_refill[i] = turn
        elif kind == "finish":
            if len(action) != 1:
                return "bad finish format"
            if s.grid[r][c] != 'D':
                return "finish not on D"
            self.finished = True             # the game ends here: no villain move, no damage
            self.t = turn
            return None
        else:
            return "unknown action %r" % (action,)

        # 3-4. villains move, damage from end-of-turn positions
        self.t = turn
        hits = sum(1 for path in s.villains if villain_at(path, turn) == self.pos)
        self.fluid -= hits * s.vdmg
        if self.fluid < 0:
            return "fluid %d < 0 at turn %d" % (self.fluid, turn)
        return None


def validate(game, plan):
    """Replay a full plan. Returns (ok, message)."""
    sim = Sim(game)
    for n, a in enumerate(plan, 1):
        err = sim.step(a)
        if err:
            return False, "turn %d: %s" % (n, err)
    if not sim.finished:
        return False, "plan does not end with ('finish',)"
    return True, "ok, %d turns, final fluid %d" % (len(plan), sim.fluid)


def test_step1():
    # Swing cost: 3 tiles, height 1 -> 4, expect 3 + 3 = 6.
    g = {
        "map": [['P', 'P', 'P', 'P', 'D']],
        "heights": [[1, 0, 0, 4, 0]],
        "spiderman": {"starting_location": (0, 0), "starting_web_fluid": 9, "max_web_fluid": 9,
                      "swing_range": 3, "villain_damage": 5},
        "villains": {"V": [(0, 1), (0, 2), (0, 3)]},     # path A,B,C
        "web_caches": [{"location": [0, 2], "refill_amount": 4, "cooldown": 2}],
    }
    p = ex1.SpiderManProblem(g)
    print("initial:", p.initial)
    print("swings from (0,0):", p.swings[0])
    cost_to_3 = [cost for dst, cost, a in p.swings[0] if dst == 3]
    assert cost_to_3 == [6], cost_to_3

    # Villain A,B,C -> A B C B A B over t = 0..5  (cells 1,2,3,2,1,2)
    print("P =", p.P, " dmg per phase:", p.dmg)
    seq = [list(p.dmg[t % p.P].keys())[0] for t in range(6)]
    assert seq == [1, 2, 3, 2, 1, 2], seq
    assert p.P == 4

    # Walls stop the scan; LCM of periods 4 and 6 is 12.
    g2 = {
        "map": [['P', 'I', 'P'], ['P', 'P', 'P'], ['P', 'P', 'D']],
        "heights": [[0] * 3] * 3,
        "spiderman": {"starting_location": (0, 0), "starting_web_fluid": 9, "max_web_fluid": 9,
                      "swing_range": 2, "villain_damage": 1},
        "villains": {"a": [(1, 0), (1, 1), (1, 2)],          # period 4
                     "b": [(2, 0), (2, 1), (2, 2), (1, 2)]},  # period 6
        "web_caches": [],
    }
    p2 = ex1.SpiderManProblem(g2)
    dsts = sorted(d for d, _, _ in p2.swings[0])
    assert dsts == [3, 6], dsts          # right is blocked by I at (0,1)
    assert p2.P == 12, p2.P
    assert p2.cache_at == {} and p2.initial[3] == ()
    print("step 1: all checks passed")


def _game(row, start, fluid, max_fluid, dmg, villains=None, caches=None, heights=None):
    """Helper: a one-row map."""
    return {
        "map": [list(row)],
        "heights": [heights or [0] * len(row)],
        "spiderman": {"starting_location": start, "starting_web_fluid": fluid,
                      "max_web_fluid": max_fluid, "swing_range": 2, "villain_damage": dmg},
        "villains": villains or {},
        "web_caches": caches or [],
    }


def test_step2():
    # (a) PDF: swing 1 tile onto a villain's end tile: 9 - 1 - 5 = 3
    p = ex1.SpiderManProblem(_game("PPPD", (0, 0), 9, 9, 5, villains={"V": [(0, 1)]}))
    s = p.result(p.initial, ("swing", (0, 1)))
    print("(a)", s)
    assert s[1] == 3, s
    # swing of 2 tiles to (0,2) has no villain: 9 - 2 = 7
    assert p.result(p.initial, ("swing", (0, 2)))[1] == 7

    # (b) PDF: refill before damage: 2 + 4 - 3 = 3 (villain stays on the start tile;
    #     no damage at time 0, but damage after the turn)
    p = ex1.SpiderManProblem(_game("PPD", (0, 0), 2, 10, 3, villains={"V": [(0, 0)]},
                                   caches=[{"location": (0, 0), "refill_amount": 4, "cooldown": 2}]))
    s = p.result(p.initial, ("refill",))
    print("(b)", s)
    assert s[1] == 3, s
    # waiting instead would give 2 - 3 < 0 -> illegal
    assert ("wait",) not in p.actions(p.initial)

    # (c) PDF: cooldown 2, refill at turn 1 -> blocked at turns 2, 3; usable at turn 4
    p = ex1.SpiderManProblem(_game("PPD", (0, 0), 5, 10, 3,
                                   caches=[{"location": (0, 0), "refill_amount": 4, "cooldown": 2}]))
    s = p.initial
    assert ("refill",) in p.actions(s)          # turn 1
    s = p.result(s, ("refill",))
    assert ("refill",) not in p.actions(s)      # turn 2
    s = p.result(s, ("wait",))
    assert ("refill",) not in p.actions(s)      # turn 3
    s = p.result(s, ("wait",))
    assert ("refill",) in p.actions(s)          # turn 4
    print("(c) cooldown ok, state before turn 4:", s)
    # refill when full is legal and caps at max
    p = ex1.SpiderManProblem(_game("PPD", (0, 0), 10, 10, 3,
                                   caches=[{"location": (0, 0), "refill_amount": 4, "cooldown": 2}]))
    assert p.result(p.initial, ("refill",))[1] == 10

    # (d) fluid exactly 0 is legal; -1 is not
    p = ex1.SpiderManProblem(_game("PPD", (0, 0), 2, 10, 3))
    assert ("swing", (0, 2)) in p.actions(p.initial)      # 2 - 2 = 0
    p = ex1.SpiderManProblem(_game("PPD", (0, 0), 1, 10, 3))
    assert ("swing", (0, 2)) not in p.actions(p.initial)  # 1 - 2 < 0

    # (e) on D: only finish; after finish: goal, no actions
    p = ex1.SpiderManProblem(_game("PPD", (0, 2), 5, 10, 3))
    assert p.actions(p.initial) == [("finish",)]
    s = p.result(p.initial, ("finish",))
    assert p.goal_test(s) and not p.goal_test(p.initial)
    assert p.actions(s) == []

    # (f) height: climbing costs, dropping is free
    p = ex1.SpiderManProblem(_game("PPD", (0, 0), 10, 10, 3, heights=[0, 3, 0]))
    assert p.result(p.initial, ("swing", (0, 1)))[1] == 10 - 1 - 3
    s = p.result(p.initial, ("swing", (0, 1)))
    assert p.result(s, ("swing", (0, 2)))[1] == 6 - 1
    print("step 2: all checks passed")


def _prefix_error(game, plan):
    """Error of the first illegal action in a (possibly unfinished) plan, or None."""
    sim = Sim(game)
    for a in plan:
        err = sim.step(a)
        if err:
            return err
    return None


def test_step3_validator():
    """Part A: the validator itself must accept legal plans and reject illegal ones."""
    g1 = non_comp_problems[0]        # 3x3, range 1, fluid 10, no villains
    ok, msg = validate(g1, [("swing", (0, 1)), ("swing", (0, 2)), ("swing", (1, 2)),
                            ("swing", (2, 2)), ("finish",)])
    assert ok and "final fluid 6" in msg, msg
    bad_plans = [
        [("swing", (1, 1))],                          # diagonal
        [("swing", (0, 2))],                          # out of range (R = 1)
        [("swing", (0, 1))],                          # no finish at the end
        [("finish",)],                                # finish not on D
        [("swing", [0, 1]), ("finish",)],             # target is a list, not a tuple
        ["wait"],                                     # action is not a tuple
        [("swing", (0, -1))],                         # leaves the map
    ]
    for plan in bad_plans:
        ok, msg = validate(g1, plan)
        assert not ok, plan
    # action after finish
    p_on_d = _game("PPD", (0, 2), 5, 10, 3)
    assert not validate(p_on_d, [("finish",), ("wait",)])[0]
    assert validate(p_on_d, [("finish",)])[0]

    # swing over a wall: problem 4, (1,0) is I
    assert _prefix_error(non_comp_problems[3], [("swing", (2, 0))]) is not None

    # PDF numbers
    g = _game("PPPD", (0, 0), 9, 9, 5, villains={"V": [(0, 1)]})
    sim = Sim(g)
    assert sim.step(("swing", (0, 1))) is None and sim.fluid == 3            # 9 - 1 - 5
    g = _game("PPD", (0, 0), 2, 10, 3, villains={"V": [(0, 0)]},
              caches=[{"location": (0, 0), "refill_amount": 4, "cooldown": 2}])
    sim = Sim(g)
    assert sim.step(("refill",)) is None and sim.fluid == 3                  # 2 + 4 - 3
    g = _game("PPD", (0, 0), 5, 10, 3,
              caches=[{"location": (0, 0), "refill_amount": 4, "cooldown": 2}])
    assert _prefix_error(g, [("refill",), ("refill",)]) is not None          # turn 2 blocked
    assert _prefix_error(g, [("refill",), ("wait",), ("refill",)]) is not None  # turn 3 blocked
    assert _prefix_error(g, [("refill",), ("wait",), ("wait",), ("refill",)]) is None  # turn 4
    # exactly 0 is legal, below 0 is not
    assert _prefix_error(_game("PPD", (0, 0), 2, 10, 3), [("swing", (0, 2))]) is None
    assert _prefix_error(_game("PPD", (0, 0), 1, 10, 3), [("swing", (0, 2))]) is not None
    # villain walk A,B,C -> A B C B A B
    assert [villain_at(["A", "B", "C"], t) for t in range(6)] == list("ABCBAB")
    print("step 3 (validator self-test): all checks passed")


def _candidates(sim):
    """Every action worth trying from here, legal or not (including too-long swings)."""
    r, c = sim.pos
    out = [("wait",), ("refill",), ("finish",)]
    for k in range(1, sim.s.R + 2):
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            out.append(("swing", (r + dr * k, c + dc * k)))
    return out


def crosscheck(game, walks, length, rng):
    """Part B: random walks through the ex1 model. At every visited state, every
    candidate action must be legal in ex1  <=>  legal in the validator, and the
    resulting position and fluid must agree. Returns the number of comparisons."""
    p = ex1.SpiderManProblem(game)
    W = p.W
    checked = 0
    for _ in range(walks):
        state, sim = p.initial, Sim(game)
        for _ in range(length):
            model = dict(p._successors(state))
            on_d = sim.s.grid[sim.pos[0]][sim.pos[1]] == 'D'
            for a in _candidates(sim):
                trial = sim.clone()
                legal_v = trial.step(a) is None
                legal_m = a in model
                if on_d and a != ("finish",):
                    # on D the model generates only finish (on purpose, see explanation.md)
                    assert not legal_m, (a, state)
                    continue
                assert legal_v == legal_m, ("MISMATCH", a, "model:", legal_m,
                                            "validator:", legal_v, "state:", state, "turn:", sim.t)
                if legal_m and not trial.finished:
                    ns = model[a]
                    assert ns[0] == trial.pos[0] * W + trial.pos[1], ("pos", a, ns, trial.pos)
                    assert ns[1] == trial.fluid, ("fluid", a, ns, trial.fluid)
                checked += 1
            if not model:
                break
            items = list(model.items())
            refills = [it for it in items if it[0] == ("refill",)]
            # bias toward refills so that cooldowns get exercised
            a, state = refills[0] if refills and rng.random() < 0.3 else rng.choice(items)
            assert sim.step(a) is None
            if sim.finished:
                assert p.goal_test(state)
                break
    return checked


def test_step3_crosscheck():
    rng = random.Random(12345)
    total = 0
    for n, game in enumerate(non_comp_problems, 1):
        k = crosscheck(game, walks=100, length=30, rng=rng)
        print("  problem %2d: %6d comparisons, no mismatch" % (n, k))
        total += k
    print("step 3 (cross-check model vs validator): %d comparisons, all agree" % total)


def solve_counted(game):
    """Build + solve one problem; also count expanded nodes (calls to _successors)."""
    import time
    t0 = time.time()
    p = ex1.create_spiderman_problem(game)
    calls = [0]
    real = p._successors

    def counted(state):
        calls[0] += 1
        return real(state)
    p._successors = counted               # instance attribute shadows the method
    node = ex1.astar_search(p, p.h)
    plan = None if node is None else [n.action for n in node.path()[1:]]
    return p, node, plan, time.time() - t0, calls[0]


def test_step4():
    known = {1: 5, 2: None, 3: 5}
    print("problem | length | expanded |   time")
    for n, game in enumerate(non_comp_problems, 1):
        p, node, plan, dt, expanded = solve_counted(game)
        length = None if plan is None else len(plan)
        print("  %5d | %6s | %8d | %5.2fs" % (n, length, expanded, dt))
        if n in known:
            assert length == known[n], (n, length, known[n])
        if plan is not None:
            ok, msg = validate(game, plan)
            assert ok, (n, msg, plan)
            assert p.h(search_node_root(p)) <= length
    print("step 4: all plans legal, known lengths match")


def search_node_root(p):
    import search
    return search.Node(p.initial)


if __name__ == "__main__":
    test_step1()
    test_step2()
    test_step3_validator()
    test_step3_crosscheck()
    test_step4()
