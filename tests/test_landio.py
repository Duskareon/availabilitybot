import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")

from landio_bot.bots import baseline_opponents  # noqa: E402
from landio_bot.game import DOWN, LEFT, NEUTRAL, RIGHT, UP, Game  # noqa: E402
from landio_bot.smart_bot import SmartBot  # noqa: E402


class Scripted:
    def __init__(self, moves):
        self.moves = list(moves)

    def decide(self, game, pid):
        return self.moves.pop(0) if self.moves else None


def make_game(*scripts, size=30):
    game = Game([Scripted(s) for s in scripts], size=size, max_ticks=500, seed=1)
    game.owner[:] = NEUTRAL
    return game


def place(game, pid, top, left, head, direction, r=1):
    game.owner[top : top + 2 * r + 1, left : left + 2 * r + 1] = pid
    game.players[pid].head = head
    game.players[pid].direction = direction


def test_loop_claims_enclosed_area():
    # Start in a 3x3 block, go up 3, right 2, down 3 back into the block.
    game = make_game([UP, UP, UP, RIGHT, RIGHT, DOWN, DOWN, DOWN])
    place(game, 0, 10, 10, (10, 10), UP)
    for _ in range(8):
        game.step()
    assert game.players[0].alive
    assert not game.players[0].trail
    # The rectangle rows 7..12, cols 10..12 is now ours, including (8,11) inside the loop.
    assert (game.owner[7:13, 10:13] == 0).all()
    assert (game.owner == 0).sum() == 18


def test_stepping_on_trail_kills_and_takes_land():
    game = make_game([UP, UP, UP, UP], [LEFT, LEFT, LEFT], size=30)
    place(game, 0, 10, 10, (10, 11), UP)
    place(game, 1, 6, 15, (7, 15), LEFT)
    # Player 0 walks up column 11 leaving a trail on rows 9, 8, 7...
    # Player 1 walks left along row 7 and crosses it.
    for _ in range(4):
        game.step()
    assert not game.players[0].alive
    assert game.players[0].killed_by == 1
    assert (game.owner == 0).sum() == 0
    assert (game.owner[10:13, 10:13] == 1).all()


def test_hitting_own_trail_or_wall_is_death():
    game = make_game([UP, UP, RIGHT, DOWN, LEFT])
    place(game, 0, 10, 10, (10, 10), UP)
    for _ in range(5):
        game.step()
    # Up to (8,10), right, down to (9,11), then left onto our own trail at (9,10).
    assert not game.players[0].alive
    assert (game.owner == 0).sum() == 0

    game = make_game([UP] * 5)
    place(game, 0, 0, 0, (1, 1), UP)
    for _ in range(3):
        game.step()
    assert not game.players[0].alive


def test_full_game_runs_and_smart_bot_competes():
    import random

    rng = random.Random(3)
    bots = [SmartBot(1)] + baseline_opponents(7, rng)
    game = Game(bots, size=40, max_ticks=300, seed=3)
    res = game.run()
    assert res.ticks <= 300
    assert sum(res.areas) <= 40 * 40
    assert res.winner is not None
