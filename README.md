# Castle Adventure

A small text-free adventure game built with [Streamlit](https://streamlit.io).
You are dropped into a randomly generated castle and have to collect
**60 gold** without dying.

The whole castle is always on screen, but under a **fog of war**: a room you
have not found yet shows a question mark instead of what is inside it. You
can only walk into the rooms joined to the one you are standing in, so the
game is about exploring blind and choosing a route: which room is worth the
risk of an enemy you cannot see yet?

- **Treasures** are worth 20 to 40 gold and can only be collected once.
- **Enemies** block their room and ask a maths problem. You have 20
  seconds to solve it.
- **A correct answer** defeats the enemy, empties the room and pays 10
  gold.
- **A wrong answer** costs 5 health. The enemy stays and asks a brand new
  problem, so a mistake hurts but never wastes the room.
- **Running out of time** costs 5 health as well, and the enemy flees,
  leaving the room empty.
- Start with 20 health. Four mistakes in one room is death, because the
  enemy keeps asking until you succeed or fall.

### Fog of war

Rooms start unexplored. The one you are standing in is always visible;
every other room shows `?` until you walk into it. That includes the
enemies, so **you can no longer see a fight coming and route around it** —
you find out the same way the gold does.

### Walls

Three rooms in every castle are solid walls. They are left out of the maze
entirely, so they hold no passages and can never block the way to a
treasure.

You find one by walking into it. Because a wall has no passage, it is never
a normal destination, so you may click any room that merely *touches* the
one you are in: either a passage was hiding and you walk in, or it is stone
and you bump into it. Bumping costs nothing — no health, no move — it just
reveals the wall, and the button then locks for the rest of the run.

---

## Requirements

- Python 3.10 or newer
- The packages in `requirements.txt` (only Streamlit)

## How to run

Use a virtual environment so the project does not depend on whatever
Python happens to be on the machine. From the project folder:

```bash
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m streamlit run app.py
```

Streamlit prints a local address, normally <http://localhost:8501>.
Open it in a browser and press **New game** to start a run. Press
`Ctrl+C` in the terminal to stop it.

> **This machine has two Python installations.** One of them has a
> half-installed Streamlit that is missing `typing_extensions`, so the
> bare `streamlit` command fails with
> `ModuleNotFoundError: No module named 'typing_extensions'`. That is
> the wrong Python. Always go through the virtual environment above, or
> through the full path of the complete installation:
>
> ```powershell
> & "C:\Users\deban\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m streamlit run app.py
> ```

## How to test

No test framework is needed. Both suites are plain Python files that
print one line per check and exit non-zero if anything fails.

```bash
python -m tests.test_game     # the rules, with no Streamlit involved
python -m tests.test_app      # the page, driven as a browser would
```

Use the same interpreter you used to start the game, for example
`.\.venv\Scripts\python -m tests.test_game`.

`tests/test_game.py` never imports Streamlit, which is the whole point of
splitting the project in two: the game logic can be checked from a
terminal, instantly, without a browser.

`tests/test_app.py` uses Streamlit's own `AppTest` to run `app.py` for
real, clicking buttons and typing answers, so it catches mistakes that
only appear in the interface.

---

## Project structure

```text
app.py               the Streamlit page: the only file that knows about it
config.py            every game number in one place
game.py              the rules: movement, combat, the clock, win and lose
models/
    operation.py     one maths problem
    treasure.py      one pile of gold
    enemy.py         one enemy, with its name and damage
    room.py          one square, and the four kinds it can be
    castle.py        the maze: rooms, passages, and what is inside them
    player.py        health, gold, and where the player stands
tests/
    test_game.py     tests for the rules
    test_app.py      tests for the page
docs/
    class-diagram.md the class diagram, in Mermaid
    class-diagram.puml the same diagram, in PlantUML, for images
requirements.txt
.venv/               created by you, not part of the code
```

### Why it is split this way

**`config.py` holds every number.** Health, damage, the gold goal, the
map size and the time limit all live in one short file. Rebalancing the
game never means hunting through the code, and a reader can understand
the whole design from a single screen.

**The model classes know nothing about the game.** `Room` knows what it
holds; `Enemy` knows how to ask a question and how to be defeated. None
of them know the player exists. That is what makes them easy to test on
their own.

**`Game` is the referee.** It is the only class allowed to change health
or gold, which means there is exactly one place to look when asking
"what happens if I walk into an enemy room?".

**`app.py` only draws.** It never invents rules and never imports
anything from `models` other than to read what is on screen. Every
widget changes the game through a **callback** that runs before the page
is drawn, so a half-drawn page can never leave the game in a strange
state.

**See the diagram.** [`docs/class-diagram.md`](docs/class-diagram.md)
draws all ten classes and how they relate, with notes on why links are
stored as ids rather than objects, and why `Game` is the only class
allowed to change health or gold. The same diagram is in
[`docs/class-diagram.puml`](docs/class-diagram.puml) for turning it into
an image.

### Two details worth knowing

**The map is a tree, built by a random depth-first search.** Every *walkable*
room is reachable from every other one by exactly one route, so the castle
can never contain an unreachable treasure or a loop that wastes time. Walls
are excluded from that tree, so the invariant is stated over the walkable
rooms only. The map always holds exactly 4 treasure rooms and 3 enemy rooms,
dealt from a fixed list rather than dice rolls, which is what guarantees a
winnable castle. The room you start in is then emptied by **trading**
its contents with an empty room, so making the start safe never quietly
removes a treasure.

**Walls are placed one at a time, and each one is checked before the next.**
A row of walls can split a 4x4 grid in two, and the depth-first search only
reaches the piece holding the starting room: a treasure stranded in the other
piece would make the run impossible to win. Measured over random castles,
that happened in **15% of them**. So a candidate wall that would disconnect
the walkable area is put back and another is tried. The same check also
rejects a wall ringed by other walls, which could never be discovered.
Building the walls before the maze is what lets the search skip them.

**The countdown subtracts from a deadline, it does not count down.**
`Game.time_remaining()` returns `deadline - time.time()`. If the page is
slow, or a refresh is skipped, the remaining time is still correct. A
counter that ticks down in a variable would slowly drift and could give
the player extra seconds for free.

The countdown lives in an `@st.fragment(run_every=0.5)`, so only that
small piece is redrawn twice a second. The answer box is deliberately
**outside** the fragment, because re-rendering a text input while
somebody is typing in it would fight the keyboard.

---

## Rebalancing the game

Everything you would normally want to change is in `config.py`:

| Setting | Effect |
| --- | --- |
| `STARTING_HEALTH` | how many mistakes you can survive |
| `ENEMY_DAMAGE` | the cost of one wrong answer or timeout |
| `GOLD_PER_ENEMY` | the reward for beating an enemy |
| `GOLD_GOAL` | the gold needed to win |
| `TREASURE_GOLD_MIN` / `_MAX` | how much a treasure is worth |
| `MAP_ROWS` / `MAP_COLUMNS` | the size of the castle |
| `TREASURE_ROOMS` / `ENEMY_ROOMS` | how the rooms are filled |
| `WALL_ROOMS` | how many rooms are solid walls |
| `ANSWER_TIME_LIMIT` | seconds allowed to solve a problem |
| `OPERAND_MIN` / `OPERAND_MAX` | how hard the maths is |
| `TIMER_REFRESH_SECONDS` | how often the countdown redraws |

To make gold come only from treasure rooms, set `GOLD_PER_ENEMY = 0`.
To make the maths easier, lower `OPERAND_MAX` in `config.py`.

`answer_current_problem` in the tests recomputes the answer from the
text the player sees, so a bug in the arithmetic cannot slip past the
test suite.
