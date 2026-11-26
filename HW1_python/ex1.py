import search
import random
import math
import itertools


ids = ["111111111", "111111111"]


class SpiderManProblem(search.Problem):
    """This class implements the Spider-Man web-swinging problem according to the
    problem description file."""

    def __init__(self, initial):
        """`initial` is the input dictionary described in the assignment.
        State = (pos, fluid, phase, cooldowns)  (decisions D1-D4 in CLAUDE.md)."""
        game = initial
        grid = game["map"]
        heights = game["heights"]
        H, W = len(grid), len(grid[0])
        self.H, self.W = H, W

        # ---- map ----
        wall = [[grid[r][c] == 'I' for c in range(W)] for r in range(H)]
        self.goal_cell = None
        for r in range(H):
            for c in range(W):
                if grid[r][c] == 'D':
                    self.goal_cell = r * W + c

        sm = game["spiderman"]
        R = sm["swing_range"]
        self.max_fluid = sm["max_web_fluid"]
        self.villain_damage = sm["villain_damage"]

        # ---- swing list per cell: (dst, base_cost, action) ----
        # base_cost = k + max(0, h_dst - h_src); villain damage is added later.
        self.swings = [[] for _ in range(H * W)]
        for r in range(H):
            for c in range(W):
                if wall[r][c]:
                    continue
                lst = self.swings[r * W + c]
                h_src = heights[r][c]
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    for k in range(1, R + 1):
                        nr, nc = r + dr * k, c + dc * k
                        if not (0 <= nr < H and 0 <= nc < W) or wall[nr][nc]:
                            break  # blocked: no longer swing in this direction either
                        cost = k + max(0, heights[nr][nc] - h_src)
                        lst.append((nr * W + nc, cost, ("swing", (nr, nc))))

        # ---- villains: cycles, P = lcm of periods, sparse dmg[phase] ----
        cycles = []
        for path in game["villains"].values():
            path = [tuple(p) for p in path]
            cyc = path + path[-2:0:-1]          # A B C D -> A B C D C B
            cycles.append([r * W + c for r, c in cyc])
        self.P = 1
        for cyc in cycles:
            self.P = math.lcm(self.P, len(cyc))
        self.dmg = []
        for t in range(self.P):
            d = {}
            for cyc in cycles:
                cell = cyc[t % len(cyc)]
                d[cell] = d.get(cell, 0) + self.villain_damage
            self.dmg.append(d)

        # ---- web caches ----
        self.cache_at = {}
        self.refill_amt = []
        self.cd_len = []
        for i, wc in enumerate(game["web_caches"]):
            r, c = tuple(wc["location"])
            self.cache_at[r * W + c] = i
            self.refill_amt.append(wc["refill_amount"])
            self.cd_len.append(wc["cooldown"])

        # ---- initial state ----
        r0, c0 = tuple(sm["starting_location"])
        start = (r0 * W + c0, sm["starting_web_fluid"], 0,
                 tuple(0 for _ in self.cd_len))
        search.Problem.__init__(self, start)

    FINISHED = (-1, 0, 0, ())

    def _successors(self, state):
        """The ONLY place where the game rules live.
        Returns a list of (action, next_state) for all legal actions."""
        pos, fluid, phase, cds = state
        if pos == -1:                      # finished: check BEFORE any table lookup
            return []
        if pos == self.goal_cell:          # on D the only useful action is finish
            return [(("finish",), self.FINISHED)]

        nphase = (phase + 1) % self.P      # villains move -> positions at time t+1
        d = self.dmg[nphase]
        ncds = tuple(x - 1 if x > 0 else 0 for x in cds)
        out = []

        for dst, cost, action in self.swings[pos]:
            nf = fluid - cost - d.get(dst, 0)
            if nf >= 0:
                out.append((action, (dst, nf, nphase, ncds)))

        nf = fluid - d.get(pos, 0)
        if nf >= 0:
            out.append((("wait",), (pos, nf, nphase, ncds)))

        i = self.cache_at.get(pos)
        if i is not None and cds[i] == 0:
            nf = min(self.max_fluid, fluid + self.refill_amt[i]) - d.get(pos, 0)
            if nf >= 0:
                rcds = ncds[:i] + (self.cd_len[i],) + ncds[i + 1:]
                out.append((("refill",), (pos, nf, nphase, rcds)))
        return out

    def actions(self, state):
        """Return the valid actions that can be executed in the given state."""
        return [a for a, _ in self._successors(state)]

    def result(self, state, action):
        """Return the state that results from executing the given action in the given state."""
        for a, s in self._successors(state):
            if a == action:
                return s
        raise ValueError("illegal action %r in state %r" % (action, state))

    def goal_test(self, state):
        """Return True if the state is a goal state."""
        return state[0] == -1

    def h(self, node):
        """
        Heuristic function for A* search.
        Estimates the minimum number of turns needed to reach the goal.
        """
        raise NotImplementedError


def create_spiderman_problem(game):
    return SpiderManProblem(game)


def astar_search(problem, heuristic):
    """Return the goal node if found, None otherwise."""
    raise NotImplementedError
