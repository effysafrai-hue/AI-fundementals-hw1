"""Local tests only. NOT submitted, never imported by ex1.py."""
import ex1


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


if __name__ == "__main__":
    test_step1()
    test_step2()
