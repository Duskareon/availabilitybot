# Land-io bot

An AI player for Land-io style territory games (claim land by leaving your
area and looping back, eliminate players by crossing their trail), plus a
headless simulator to test it in.

This runs against the included simulator only. It does not connect to or
automate Discord's Land-io activity. Automating it would break Discord's
rules, and in public lobbies it would be cheating against real people.

## Rules the simulator follows

- 16 players on a 64×64 grid, 1000 ticks per game (about 5 minutes at 3–4 moves a second).
- Each tick every player moves one cell. You can't reverse.
- Outside your land you leave a trail. Getting back to your land claims the
  trail and everything it encloses.
- Cross someone's trail and they're out. The killer gets all of their land.
  Hitting your own trail or the wall knocks you out and your land goes neutral.
- Head-on collision: whoever is standing in their own land survives. If neither is, both are out.
- Most land when time runs out wins.

## How the smart bot plays (`smart_bot.py`)

Every tick it chooses one of these, in priority order:

1. **Hunt.** For each enemy that is out with a trail, it compares how fast it
   can reach any trail cell with how fast that enemy can get home. If it gets
   there first and the chase doesn't leave its own trail open, it goes for
   the kill.
2. **Stay safe.** Outside its land it walks its planned path home and counts
   the ticks. If any enemy head could reach its trail (or that path) within
   those ticks plus a margin, it drops the plan and heads home.
3. **Expand.** At home it tests a few hundred rectangular loops (4 directions ×
   2 turn sides × 9×9 sizes). For each one it works out the exact land the
   loop would enclose, drops any loop an enemy could cut, and picks the best
   land per tick. Enemy land counts extra, and the current leader's land
   counts extra again.
4. **Play to the scoreboard.** It never starts a loop it can't finish before
   time runs out. It takes one extra tick of safety margin while it's leading,
   and it stays inside its land for the last few seconds when it's
   comfortably ahead.

## Results

Win rates are measured with `evaluate.py`. Opponents are a mix of four
baseline styles (random walkers, paper.io-style rectangle loopers, cautious
loopers that retreat when threatened, and hunters that chase trails). Fair
share in a 16-player game is 1/16 ≈ 6%.

| Setup | Games | Smart bot wins | Survived | Avg. map share |
|---|---|---|---|---|
| vs 15 baseline bots | 50 | **50 (100%)** | 100% | 34.7% |
| vs 3 copies of itself + 12 baseline bots | 40 | 7 (18%) | 98% | 12.7% |

In the second setup, the four smart bots together won 38 of 40 games. Fair
share for any one of four equal bots is 25%, and the 18% measured is within
noise of that over 40 games. So against equally good players it is even,
not dominant. Its edge is over weaker play.

## Run it

```bash
pip install -r landio_bot/requirements.txt
python -m landio_bot.evaluate --games 50                  # vs 15 baseline bots
python -m landio_bot.evaluate --games 30 --smart-rivals 3 # 3 of the 15 are copies of the smart bot
python -m landio_bot.evaluate --games 1 --show            # print the final board
```

To plug in your own bot, write a class with `decide(game, pid) -> direction`
(0 up, 1 right, 2 down, 3 left). An optional `reset(game, pid)` is called at
spawn. Then pass it to `Game([...])`.
