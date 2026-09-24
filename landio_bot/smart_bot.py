"""The Land-io player that aims to win.

Each tick it picks one of three modes:

1. Hunt: if it can reach an enemy trail before that enemy gets home, and
   doing so keeps its own trail safe, it goes for the kill (the killer gets
   all of the victim's land, which is the biggest swing in the game).
2. Retreat: while outside its land it keeps a safety check. The number of
   ticks it needs to get home, along the path it would take, must stay
   below the number of ticks any enemy head needs to touch its trail. If
   the plan would break that rule it heads straight home.
3. Expand: at home it tries many rectangular loops, works out how much land
   each would enclose, drops the ones an enemy could cut, and picks the one
   with the best land per tick. Enemy land counts extra, and the leader's
   land extra again, because the game is won on relative size.

It also plays to the score: it never starts a loop that cannot finish before
the clock runs out, and it takes fewer risks while it is winning.
"""

from __future__ import annotations

import random

import numpy as np

from .bots import INF, bfs, legal_moves, step
from .game import enclosed_by, reverse

SIZES = (2, 3, 4, 5, 6, 8, 10, 13, 16)


class SmartBot:
    name = "Smart"

    def __init__(self, seed: int | None = None, margin: int = 2, hunt_range: int = 20):
        self.rng = random.Random(seed)
        self.margin = margin
        self.hunt_range = hunt_range

    def reset(self, game, pid):
        self.plan: list[int] = []

    # ------------------------------------------------------------------ main
    def decide(self, game, pid):
        p = game.players[pid]
        own = game.owner == pid
        mytrail = game.trail == pid
        enemies = [q for q in game.players if q.alive and q.pid != pid]
        heads = np.zeros_like(own)
        for q in enemies:
            heads[q.head] = True
        passable = np.ones_like(own)
        self.enemy_dist = bfs(heads, passable)
        self.home_dist = bfs(own, ~mytrail)
        self.ticks_left = game.max_ticks - game.tick
        areas = game.areas()
        rival = max(enemies, key=lambda q: areas[q.pid]) if enemies else None
        leading = rival is None or areas[pid] > areas[rival.pid]
        margin = self.margin + (1 if leading else 0)

        moves = legal_moves(game, pid)
        if not moves:
            return p.direction

        d = self._hunt(game, pid, moves, areas, mytrail, margin)
        if d is not None:
            self.plan = []
            return d

        at_home = bool(own[p.head])
        if not at_home:
            if self.plan and self.plan[0] in moves and self._safe(game, pid, step(p.head, self.plan[0]), margin):
                return self.plan.pop(0)
            self.plan = []
            return self._go_home(game, pid, moves)

        # Winning comfortably near the end: sit tight.
        if leading and rival is not None and self.ticks_left < 40 and areas[pid] > 1.15 * areas[rival.pid]:
            self.plan = []
            return self._wander(game, pid, moves, own)

        if self.plan and self.plan[0] in moves:
            nxt = step(p.head, self.plan[0])
            if own[nxt] or self._safe(game, pid, nxt, margin):
                return self.plan.pop(0)
        self.plan = self._make_plan(game, pid, own, areas, rival, margin)
        if self.plan:
            return self.plan.pop(0)
        return self._wander(game, pid, moves, own)

    # --------------------------------------------------------------- safety
    def _path_home(self, game, cell):
        """Cells walked from `cell` back to land, following home_dist downhill."""
        path = [cell]
        cur = cell
        seen = {cell}
        while self.home_dist[cur] > 0:
            nxt = None
            for d in range(4):
                c = step(cur, d)
                if game.in_bounds(c) and c not in seen and self.home_dist[c] < self.home_dist[cur]:
                    nxt = c
                    break
            if nxt is None:
                return None
            path.append(nxt)
            seen.add(nxt)
            cur = nxt
        return path

    def _safe(self, game, pid, cell, margin) -> bool:
        """Can we step on `cell` and still get home before anyone cuts us?"""
        p = game.players[pid]
        if game.owner[cell] == pid:
            return all(self.enemy_dist[c] > 1 for c in p.trail)
        if self.home_dist[cell] >= INF:
            return False
        path = self._path_home(game, cell)
        if path is None:
            return False
        finish = len(path)  # ticks until we are back on our land
        if finish > self.ticks_left:
            return False
        exposed = min(self.enemy_dist[c] for c in path[:-1])
        if p.trail:
            exposed = min(exposed, min(self.enemy_dist[c] for c in p.trail))
        return finish + margin < exposed

    def _go_home(self, game, pid, moves):
        p = game.players[pid]

        def key(d):
            c = step(p.head, d)
            return (self.home_dist[c], -self.enemy_dist[c], self.rng.random())

        return min(moves, key=key)

    def _wander(self, game, pid, moves, own):
        """Drift around inside our land, away from the map edge."""
        p = game.players[pid]
        inside = [d for d in moves if own[step(p.head, d)]]
        if not inside:
            safe = [d for d in moves if self._safe(game, pid, step(p.head, d), 0)]
            return self._go_home(game, pid, safe or moves)
        n = game.size

        def key(d):
            c = step(p.head, d)
            edge = min(c[0], c[1], n - 1 - c[0], n - 1 - c[1])
            return (-min(edge, 3), self.rng.random())

        return min(inside, key=key)

    # ----------------------------------------------------------------- hunt
    def _hunt(self, game, pid, moves, areas, mytrail, margin):
        p = game.players[pid]
        dist_me = bfs(self._mask(game, [p.head]), ~mytrail, max_d=self.hunt_range)
        best = None
        for q in game.players:
            if not q.alive or q.pid == pid or not q.trail:
                continue
            reach = min(dist_me[c] for c in q.trail)
            if reach > self.hunt_range:
                continue
            q_home = bfs(game.owner == q.pid, game.trail != q.pid, max_d=reach + 1)[q.head]
            if reach > q_home:
                continue
            score = (areas[q.pid] + len(q.trail)) / reach
            if best is None or score > best[0]:
                best = (score, q)
        if best is None:
            return None
        q = best[1]
        to_trail = bfs(self._mask(game, q.trail), ~mytrail)
        options = []
        for d in moves:
            c = step(p.head, d)
            hit = game.trail[c] == q.pid
            if not hit and to_trail[c] >= to_trail[p.head]:
                continue
            # Only chase while our own trail stays safe: the target hunts too.
            if hit:
                ok = all(self.enemy_dist[x] > 1 for x in p.trail) and (
                    game.owner[c] == pid or self.enemy_dist[c] > 1
                )
            else:
                ok = self._safe(game, pid, c, margin)
            if ok:
                options.append((not hit, to_trail[c], self.rng.random(), d))
        return min(options)[3] if options else None

    @staticmethod
    def _mask(game, cells):
        m = np.zeros((game.size, game.size), dtype=bool)
        for c in cells:
            m[c] = True
        return m

    # --------------------------------------------------------------- expand
    def _make_plan(self, game, pid, own, areas, rival, margin):
        p = game.players[pid]
        weight = np.ones((game.size, game.size), dtype=np.float32)
        weight[(game.owner >= 0) & ~own] = 1.6
        if rival is not None:
            weight[game.owner == rival.pid] = 2.2
        best_score, best_plan = 0.0, []
        for d0 in range(4):
            if d0 == reverse(p.direction):
                continue
            for side in ((d0 + 1) % 4, (d0 + 3) % 4):
                for a in SIZES:
                    for b in SIZES:
                        res = self._simulate(game, pid, own, d0, side, a, b)
                        if res is None:
                            continue
                        plan, trail, finish = res
                        if finish > self.ticks_left - 1:
                            continue
                        exposed = min(self.enemy_dist[c] for c in trail)
                        if finish + margin >= exposed:
                            continue
                        solid = own.copy()
                        for c in trail:
                            solid[c] = True
                        gained = (enclosed_by(solid) | solid) & ~own
                        value = float(weight[gained].sum())
                        score = value / (len(plan) + 4)
                        if score > best_score:
                            best_score, best_plan = score, plan
        return best_plan

    def _simulate(self, game, pid, own, d0, side, a, b):
        """Walk the loop d0*a, side*b, back until home. Returns (moves, trail, ticks)."""
        p = game.players[pid]
        cur = p.head
        moves: list[int] = []
        trail: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()

        def walk(d):
            nonlocal cur
            nxt = step(cur, d)
            if not game.in_bounds(nxt) or nxt in seen or game.trail[nxt] == pid:
                return None
            cur = nxt
            moves.append(d)
            if own[cur]:
                return "home" if trail else "inside"
            trail.append(cur)
            seen.add(cur)
            return "out"

        # Leave the land heading d0 (walking through our own land first).
        for _ in range(game.size):
            r = walk(d0)
            if r is None:
                return None
            if r == "out":
                break
        else:
            return None
        legs = ((d0, a - 1), (side, b), (reverse(d0), a + 30), (reverse(side), b + 30))
        for d, n in legs:
            for _ in range(n):
                r = walk(d)
                if r is None:
                    return None
                if r == "home":
                    return moves, trail, len(moves)
        return None
