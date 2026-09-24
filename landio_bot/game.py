"""A headless simulator of Land-io style territory games.

Rules (modelled on Discord's Land-io activity):
- Players move one cell per tick on a square grid and cannot reverse.
- Outside their own land a player leaves a trail. Getting back to their own
  land claims the trail plus every area it encloses.
- Stepping on another player's trail eliminates that player, and the killer
  takes all of the victim's land. Hitting your own trail or the wall
  eliminates you and your land becomes neutral.
- Two heads on the same cell: a player standing in their own land survives,
  everyone else there dies.
- A player whose land drops to zero is eliminated.
- The game ends after a fixed number of ticks (or when one player is left).
  The player with the most land wins.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

UP, RIGHT, DOWN, LEFT = 0, 1, 2, 3
DIRS = ((-1, 0), (0, 1), (1, 0), (0, -1))
NEUTRAL = -1


def reverse(d: int) -> int:
    return (d + 2) % 4


def enclosed_by(solid: np.ndarray) -> np.ndarray:
    """Cells not in `solid` that cannot reach the map edge without crossing it."""
    labels, _ = ndimage.label(~solid)
    edge = np.unique(
        np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1]))
    )
    return (labels > 0) & ~np.isin(labels, edge)


@dataclass
class Player:
    pid: int
    name: str
    head: tuple[int, int]
    direction: int
    alive: bool = True
    trail: list[tuple[int, int]] = field(default_factory=list)
    killed_by: int | None = None
    kills: int = 0
    died_at: int | None = None


class Game:
    def __init__(
        self,
        bots,
        size: int = 64,
        max_ticks: int = 1000,
        start_radius: int = 2,
        seed: int | None = None,
    ):
        self.size = size
        self.max_ticks = max_ticks
        self.tick = 0
        self.rng = random.Random(seed)
        self.owner = np.full((size, size), NEUTRAL, dtype=np.int16)
        self.trail = np.full((size, size), NEUTRAL, dtype=np.int16)
        self.bots = list(bots)
        self.players: list[Player] = []
        self._spawn(start_radius)

    # ------------------------------------------------------------------ setup
    def _spawn(self, r: int) -> None:
        spots: list[tuple[int, int]] = []
        margin = r + 3
        min_gap = 2 * r + 5
        for pid, bot in enumerate(self.bots):
            for _ in range(10_000):
                p = (
                    self.rng.randint(margin, self.size - 1 - margin),
                    self.rng.randint(margin, self.size - 1 - margin),
                )
                if all(max(abs(p[0] - q[0]), abs(p[1] - q[1])) >= min_gap for q in spots):
                    break
            else:
                raise ValueError("map too small for this many players")
            spots.append(p)
            self.owner[p[0] - r : p[0] + r + 1, p[1] - r : p[1] + r + 1] = pid
            name = getattr(bot, "name", type(bot).__name__)
            self.players.append(Player(pid, name, p, self.rng.randrange(4)))
            if hasattr(bot, "reset"):
                bot.reset(self, pid)

    # ------------------------------------------------------------- queries
    def in_bounds(self, cell: tuple[int, int]) -> bool:
        return 0 <= cell[0] < self.size and 0 <= cell[1] < self.size

    def areas(self) -> np.ndarray:
        """Land count per player id."""
        return np.bincount(
            (self.owner.ravel() + 1).astype(np.int64), minlength=len(self.players) + 1
        )[1:]

    def alive_ids(self) -> list[int]:
        return [p.pid for p in self.players if p.alive]

    @property
    def over(self) -> bool:
        return self.tick >= self.max_ticks or len(self.alive_ids()) <= 1

    # ---------------------------------------------------------------- tick
    def step(self) -> None:
        alive = [p for p in self.players if p.alive]
        new_head: dict[int, tuple[int, int]] = {}
        for p in alive:
            d = self.bots[p.pid].decide(self, p.pid)
            if d is None or d not in range(4) or d == reverse(p.direction):
                d = p.direction
            p.direction = d
            dr, dc = DIRS[d]
            new_head[p.pid] = (p.head[0] + dr, p.head[1] + dc)

        deaths: dict[int, int | None] = {}  # victim -> killer (None = no killer)

        def kill(victim: int, killer: int | None) -> None:
            if victim not in deaths:
                deaths[victim] = killer

        for pid, cell in new_head.items():
            if not self.in_bounds(cell):
                kill(pid, None)
                continue
            t = int(self.trail[cell])
            if t == pid:
                kill(pid, None)
            elif t != NEUTRAL:
                kill(t, pid)

        by_cell: dict[tuple[int, int], list[int]] = {}
        for pid, cell in new_head.items():
            if self.in_bounds(cell):
                by_cell.setdefault(cell, []).append(pid)
        for cell, pids in by_cell.items():
            if len(pids) < 2:
                continue
            home = [q for q in pids if self.owner[cell] == q]
            for q in pids:
                if q not in home:
                    kill(q, home[0] if home else None)

        for victim, killer in deaths.items():
            if killer is not None and killer in deaths:
                killer = None
            self._eliminate(victim, killer)

        for p in alive:
            if not p.alive:
                continue
            p.head = new_head[p.pid]
            if self.owner[p.head] == p.pid:
                if p.trail:
                    self._capture(p)
            else:
                p.trail.append(p.head)
                self.trail[p.head] = p.pid

        areas = self.areas()
        for p in self.players:
            if p.alive and areas[p.pid] == 0:
                self._eliminate(p.pid, None)

        self.tick += 1

    def _eliminate(self, pid: int, killer: int | None) -> None:
        p = self.players[pid]
        if not p.alive:
            return
        p.alive = False
        p.killed_by = killer
        p.died_at = self.tick
        self.trail[self.trail == pid] = NEUTRAL
        p.trail.clear()
        self.owner[self.owner == pid] = NEUTRAL if killer is None else killer
        if killer is not None:
            self.players[killer].kills += 1

    def _capture(self, p: Player) -> None:
        for cell in p.trail:
            self.owner[cell] = p.pid
            self.trail[cell] = NEUTRAL
        p.trail.clear()
        self.owner[enclosed_by(self.owner == p.pid)] = p.pid

    # ----------------------------------------------------------------- run
    def run(self) -> "GameResult":
        while not self.over:
            self.step()
        return self.result()

    def result(self) -> "GameResult":
        areas = self.areas()
        alive = self.alive_ids()
        if len(alive) == 1:
            winner = alive[0]
        else:
            winner = max(alive, key=lambda i: areas[i]) if alive else None
        return GameResult(winner, areas.tolist(), [p.alive for p in self.players], self.tick)

    def render(self) -> str:
        """ASCII picture: letters are land, lowercase-dotted trails, @ heads."""
        glyph = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        rows = []
        heads = {p.head: p.pid for p in self.players if p.alive}
        for r in range(self.size):
            row = []
            for c in range(self.size):
                if (r, c) in heads:
                    row.append("@")
                elif self.trail[r, c] != NEUTRAL:
                    row.append(glyph[self.trail[r, c] % 26].lower())
                elif self.owner[r, c] != NEUTRAL:
                    row.append(glyph[self.owner[r, c] % 26])
                else:
                    row.append(".")
            rows.append("".join(row))
        return "\n".join(rows)


@dataclass
class GameResult:
    winner: int | None
    areas: list[int]
    alive: list[bool]
    ticks: int
