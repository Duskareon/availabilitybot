"""Play many games and report how often the smart bot wins.

    python -m landio_bot.evaluate --games 100
    python -m landio_bot.evaluate --games 1 --show   # watch the final board
"""

from __future__ import annotations

import argparse
import random
import time
from collections import Counter

from .bots import baseline_opponents
from .game import Game
from .smart_bot import SmartBot


def play(seed: int, players: int, size: int, ticks: int, smart_rivals: int = 0):
    rng = random.Random(seed)
    rivals = [SmartBot(rng.randrange(1 << 30)) for _ in range(smart_rivals)]
    for r in rivals:
        r.name = "SmartRival"
    bots = [SmartBot(rng.randrange(1 << 30))] + rivals + baseline_opponents(players - 1 - smart_rivals, rng)
    order = list(range(players))
    rng.shuffle(order)  # the smart bot should not always spawn in the same slot
    bots = [bots[i] for i in order]
    game = Game(bots, size=size, max_ticks=ticks, seed=seed)
    smart = order.index(0)
    return game, smart, game.run()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=50)
    ap.add_argument("--players", type=int, default=16)
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--ticks", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--smart-rivals", type=int, default=0, help="how many opponents are copies of the smart bot")
    ap.add_argument("--show", action="store_true", help="print the final board of each game")
    args = ap.parse_args()

    wins = 0
    survived = 0
    share = 0.0
    winners: Counter[str] = Counter()
    start = time.time()
    for i in range(args.games):
        game, smart, res = play(args.seed + i, args.players, args.size, args.ticks, args.smart_rivals)
        won = res.winner == smart
        wins += won
        survived += res.alive[smart]
        share += res.areas[smart] / (args.size * args.size)
        winner = game.players[res.winner].name if res.winner is not None else "nobody"
        winners[winner] += 1
        if args.show:
            print(game.render())
        print(
            f"game {i + 1:3d}: {'WIN ' if won else 'loss'}  "
            f"land {res.areas[smart]:5d} ({res.areas[smart] / args.size**2:5.1%})  "
            f"{'alive' if res.alive[smart] else 'dead '}  kills {game.players[smart].kills}  "
            f"winner {winner}",
            flush=True,
        )
    n = args.games
    print()
    print(f"Smart bot won {wins}/{n} games ({wins / n:.0%}) against {args.players - 1} opponents")
    print(f"survived {survived / n:.0%} of games, average map share {share / n:.1%}")
    print(f"winners: {dict(winners)}   ({time.time() - start:.1f}s)")


if __name__ == "__main__":
    main()
