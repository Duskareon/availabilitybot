"""Grid helpers and the baseline opponents the smart bot is tested against."""

from __future__ import annotations

import random

import numpy as np

from .game import DIRS, reverse

INF = 10**6


def bfs(sources: np.ndarray, passable: np.ndarray, max_d: int | None = None) -> np.ndarray:
    """Steps from the nearest source to every cell, moving only through `passable`.

    Sources always count as distance 0. Unreached cells get INF.
    """
    dist = np.full(sources.shape, INF, dtype=np.int32)
    dist[sources] = 0
    visited = sources.copy()
    frontier = sources
    d = 0
    while frontier.any() and (max_d is None or d < max_d):
        d += 1
        nb = np.zeros_like(frontier)
        nb[1:] |= frontier[:-1]
        nb[:-1] |= frontier[1:]
        nb[:, 1:] |= frontier[:, :-1]
        nb[:, :-1] |= frontier[:, 1:]
        nb &= passable & ~visited
        dist[nb] = d
        visited |= nb
        frontier = nb
    return dist


def step(cell: tuple[int, int], d: int) -> tuple[int, int]:
    return cell[0] + DIRS[d][0], cell[1] + DIRS[d][1]


def legal_moves(game, pid: int) -> list[int]:
    """Moves that do not reverse, leave the map or hit our own trail."""
    p = game.players[pid]
    out = []
    for d in range(4):
        if d == reverse(p.direction):
            continue
        c = step(p.head, d)
        if game.in_bounds(c) and game.trail[c] != pid:
            out.append(d)
    return out


def home_distance(game, pid: int) -> np.ndarray:
    return bfs(game.owner == pid, game.trail != pid)


def move_towards(game, pid: int, dist: np.ndarray, rng: random.Random) -> int:
    """Legal move that lowers `dist` the most (random tie-break)."""
    p = game.players[pid]
    moves = legal_moves(game, pid)
    if not moves:
        return p.direction
    best = min(dist[step(p.head, d)] for d in moves)
    return rng.choice([d for d in moves if dist[step(p.head, d)] == best])


class RandomWalker:
    """Wanders with occasional turns and heads home once its trail gets long."""

    name = "Walker"

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def reset(self, game, pid):
        self.limit = self.rng.randint(6, 25)

    def decide(self, game, pid):
        p = game.players[pid]
        if len(p.trail) >= self.limit:
            d = move_towards(game, pid, home_distance(game, pid), self.rng)
            if game.owner[step(p.head, d)] == pid:
                self.limit = self.rng.randint(6, 25)
            return d
        moves = legal_moves(game, pid)
        if not moves:
            return p.direction
        if p.direction in moves and self.rng.random() < 0.8:
            return p.direction
        return self.rng.choice(moves)


class Looper:
    """The classic paper.io style bot: draws random rectangles off its land.

    With `cautious=True` it cuts a loop short when an enemy head is closer
    to it than the way home is long.
    """

    def __init__(self, seed: int | None = None, cautious: bool = False, max_side: int = 14):
        self.rng = random.Random(seed)
        self.cautious = cautious
        self.max_side = max_side
        self.name = "Cautious" if cautious else "Looper"

    def reset(self, game, pid):
        self.plan: list[int] = []

    def _new_plan(self, direction: int) -> list[int]:
        d0 = self.rng.choice([d for d in range(4) if d != reverse(direction)])
        side = (d0 + self.rng.choice((1, 3))) % 4
        a = self.rng.randint(2, self.max_side)
        b = self.rng.randint(2, self.max_side)
        return [d0] * a + [side] * b + [reverse(d0)] * (a + 2)

    def _threatened(self, game, pid) -> bool:
        p = game.players[pid]
        if not p.trail:
            return False
        hd = home_distance(game, pid)[p.head]
        for q in game.players:
            if q.alive and q.pid != pid:
                near = min(abs(q.head[0] - c[0]) + abs(q.head[1] - c[1]) for c in p.trail)
                if near <= hd + 2:
                    return True
        return False

    def decide(self, game, pid):
        p = game.players[pid]
        at_home = game.owner[p.head] == pid
        if at_home and not self.plan:
            self.plan = self._new_plan(p.direction)
        if not at_home and (not self.plan or (self.cautious and self._threatened(game, pid))):
            self.plan = []
            return move_towards(game, pid, home_distance(game, pid), self.rng)
        d = self.plan.pop(0)
        if d not in legal_moves(game, pid):
            self.plan = []
            if at_home:
                moves = legal_moves(game, pid)
                return self.rng.choice(moves) if moves else p.direction
            return move_towards(game, pid, home_distance(game, pid), self.rng)
        return d


class Hunter(Looper):
    """A cautious looper that also chases enemy trails it can reach first."""

    def __init__(self, seed: int | None = None):
        super().__init__(seed, cautious=True, max_side=10)
        self.name = "Hunter"

    def decide(self, game, pid):
        p = game.players[pid]
        best = None
        for q in game.players:
            if not q.alive or q.pid == pid or not q.trail:
                continue
            cell = min(q.trail, key=lambda c: abs(c[0] - p.head[0]) + abs(c[1] - p.head[1]))
            mine = abs(cell[0] - p.head[0]) + abs(cell[1] - p.head[1])
            theirs = len(q.trail) // 2 + 1  # rough guess of how far they are from home
            if mine <= 12 and mine < theirs and (best is None or mine < best[0]):
                best = (mine, cell)
        if best is not None:
            target = np.zeros_like(game.owner, dtype=bool)
            target[best[1]] = True
            self.plan = []
            return move_towards(game, pid, bfs(target, game.trail != pid), self.rng)
        return super().decide(game, pid)


def baseline_opponents(n: int, rng: random.Random) -> list:
    """A mixed field of opponents, as varied as a public lobby."""
    kinds = [
        lambda s: RandomWalker(s),
        lambda s: Looper(s),
        lambda s: Looper(s, cautious=True),
        lambda s: Hunter(s),
    ]
    return [kinds[i % len(kinds)](rng.randrange(1 << 30)) for i in range(n)]
