"""Smoke test of the Streamlit interface.

The rules are already covered by ``tests/test_game.py``. This file only
checks that the *page* behaves: that the map is always drawn, that
clicking a room walks there, that a fight can be solved from the text
box, that the run ends, and that "New game" starts over.

It drives the real Streamlit app through ``AppTest``, which runs
``app.py`` exactly as the browser would.

    python -m tests.test_app
"""

import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from config import Config
from game import GameState
from tests.test_game import solve

# AppTest resolves a relative path against the file that calls it, which
# would be this tests folder, so the project root is worked out here.
APP_PATH = Path(__file__).resolve().parent.parent / "app.py"

# Driving a Streamlit page means running the whole script many times,
# which is slow. On a slow machine that can outlast the 20 second answer
# deadline, and a correct answer would then be judged as a timeout. The
# clock is therefore held still while an answer is submitted. Any
# constant below the real clock works, because the deadline was already
# stored using the real time when the fight began.
FROZEN_NOW = 1_000_000

# Each test is a function that receives a freshly started app.
TESTS = []


def test(function):
    """Register a function as a test.

    This is the same tiny harness idea as ``tests.test_game``: no
    framework, just a list of functions to call.
    """
    TESTS.append(function)
    return function


def start():
    """Return a fresh run of the app."""
    return AppTest.from_file(str(APP_PATH), default_timeout=60).run()


def game_of(app):
    """Return the engine object the page is showing."""
    return app.session_state["game"]


def click_room(app, room_id):
    """Click one room of the map, exactly as a player would."""
    app.button(key=f"room_{room_id}").click().run()


def answer_current_problem(app):
    """Type the right answer into the box and press Solve."""
    question = game_of(app).current_room().enemy.question
    app.text_input[0].set_value(solve(question)).run()
    with patch("game.time.time", return_value=FROZEN_NOW):
        app.button(key="solve").click().run()


def answer_wrongly(app):
    """Type a wrong answer into the box and press Solve."""
    app.text_input[0].set_value("1000").run()
    with patch("game.time.time", return_value=FROZEN_NOW):
        app.button(key="solve").click().run()


def walk_to(app, goal_id, finish_fight=True):
    """Walk all the way to ``goal_id``, solving anything on the way.

    ``finish_fight=False`` stops as soon as the goal is reached, leaving
    any problem there unsolved, which is what a test needs when it wants
    to fight the enemy itself.

    The walk gives up the moment the run is over, because after a win
    every map button is disabled and there is nothing left to click.
    """
    start_id = game_of(app).player.position
    for room_id in steps_to(game_of(app).castle, start_id, goal_id):
        if game_of(app).state is not GameState.PLAYING:
            return
        click_room(app, room_id)
        if not finish_fight and game_of(app).player.position == goal_id:
            return
        while game_of(app).in_combat:
            answer_current_problem(app)


def steps_to(castle, start_id, goal_id):
    """Return the rooms to click through to get from start to goal.

    A breadth-first search, so the route only ever uses real passages
    and is as short as possible.
    """
    if start_id == goal_id:
        return []
    previous = {start_id: None}
    queue = [start_id]
    while queue:
        current = queue.pop(0)
        for neighbour in castle.neighbours_of(current):
            if neighbour in previous:
                continue
            previous[neighbour] = current
            if neighbour == goal_id:
                path = [goal_id]
                while previous[path[-1]] is not None:
                    path.append(previous[path[-1]])
                return list(reversed(path))[1:]
            queue.append(neighbour)
    return []


# --- The tests ----------------------------------------------------

@test
def test_the_page_loads_with_no_error():
    """The first visit draws the title, the map and the numbers."""
    app = start()
    assert not app.exception, app.exception
    assert app.title[0].value == "Castle Adventure"
    assert [metric.label for metric in app.metric] == [
        "Health", "Gold", "Room", "Enemies beaten",
    ]
    assert app.metric[0].value == str(Config.STARTING_HEALTH)
    assert app.metric[1].value == "0"


@test
def test_the_whole_map_is_always_drawn():
    """All 16 rooms are on the page, and only reachable ones are live."""
    app = start()
    game = game_of(app)
    expected = Config.MAP_ROWS * Config.MAP_COLUMNS
    rooms = [b for b in app.button if b.key.startswith("room_")]

    assert len(rooms) == expected, [b.key for b in rooms]

    reachable = set(game.castle.neighbours_of(game.player.position))
    clickable = {b.key for b in rooms if not b.disabled}
    assert clickable == {f"room_{i}" for i in reachable}, clickable

    # The room the player stands in is shown as pressed and cannot be
    # clicked, so the page never leaves the player unsure where they are.
    here = app.button(key=f"room_{game.player.position}")
    assert here.disabled is True
    assert here.label == "You"


@test
def test_a_passage_can_be_walked_through():
    """Clicking a connected room moves the player and tells the story."""
    app = start()
    neighbour = game_of(app).castle.neighbours_of(
        game_of(app).player.position
    )[0]

    click_room(app, neighbour)

    assert not app.exception, app.exception
    assert game_of(app).player.position == neighbour
    assert app.metric[2].value == str(neighbour)
    # The page says what was found, and the log keeps a record.
    assert app.info, "no message was shown"
    assert len(game_of(app).log) > 1


def meet_an_enemy():
    """Return a page where the player is standing in a live fight.

    Walking to an enemy can end the run early, because the route may
    cross enough treasure to win on the way. That is a correct game, not
    a bug, so a fresh castle is tried until a fight is actually waiting.
    """
    for _ in range(30):
        app = start()
        enemy_room = next(
            (room.room_id
             for room in game_of(app).castle.rooms
             if room.has_live_enemy()),
            None,
        )
        if enemy_room is None:
            continue
        walk_to(app, enemy_room, finish_fight=False)
        if game_of(app).in_combat:
            return app
    raise AssertionError("no fight could be reached in 30 tries")


@test
def test_a_fight_can_be_solved_from_the_page():
    """Walking into an enemy shows a problem that Solve accepts."""
    app = meet_an_enemy()
    enemy_room = game_of(app).current_room().room_id

    assert app.error, "the enemy was not shown"
    assert app.text_input, "there was no box to type in"
    assert game_of(app).player.position == enemy_room

    # AppTest cannot see progress bars, so the countdown is checked
    # through the clock itself.
    remaining = game_of(app).time_remaining()
    assert 0 < remaining <= Config.ANSWER_TIME_LIMIT, remaining

    health_before = game_of(app).player.health
    beaten_before = game_of(app).enemies_defeated
    gold_before = game_of(app).player.gold
    answer_current_problem(app)

    assert not game_of(app).in_combat, "the fight is still going"
    # The walk to this room may have beaten other enemies, so the count
    # is compared before and after rather than assumed to be one.
    assert game_of(app).enemies_defeated == beaten_before + 1
    assert game_of(app).player.gold == gold_before + Config.GOLD_PER_ENEMY
    assert game_of(app).player.health == health_before


@test
def test_a_wrong_answer_costs_health_and_stays_on_the_page():
    """A bad answer hurts, and the player gets a second try."""
    app = meet_an_enemy()
    health_before = game_of(app).player.health

    answer_wrongly(app)

    assert game_of(app).player.health == (
        health_before - Config.ENEMY_DAMAGE
    )
    assert game_of(app).in_combat, "the fight should still be on"
    assert app.text_input, "the box should still be there"


@test
def test_a_full_playthrough_reaches_a_victory_screen():
    """Collecting the goal shows the closing screen, not a crash."""
    app = start()

    for room in list(game_of(app).castle.rooms):
        if game_of(app).state is not GameState.PLAYING:
            break
        if room.room_id == game_of(app).player.position:
            continue
        walk_to(app, room.room_id)

    game = game_of(app)
    assert game.state is GameState.VICTORY, game.state
    assert game.player.gold >= Config.GOLD_GOAL
    assert app.success, "no victory banner was shown"
    # Nothing can be clicked any more, so the run is really over.
    assert all(b.disabled for b in app.button
               if b.key and b.key.startswith("room_"))


@test
def test_new_game_starts_over():
    """The restart button throws the old run away."""
    app = start()
    neighbour = game_of(app).castle.neighbours_of(
        game_of(app).player.position
    )[0]
    click_room(app, neighbour)
    assert game_of(app).rooms_visited > 1

    app.button(key="new_game").click().run()

    game = game_of(app)
    assert game.rooms_visited == 1
    assert game.player.gold == 0
    assert game.player.health == Config.STARTING_HEALTH
    assert game.state is GameState.PLAYING
    assert not app.exception, app.exception


@test
def test_the_page_never_leaks_a_crash_over_many_runs():
    """Fifty random castle builds all draw without an exception."""
    for _ in range(50):
        app = start()
        assert not app.exception, app.exception
        assert app.title[0].value == "Castle Adventure"


# --- Runner -------------------------------------------------------

def main():
    """Run every registered test and report the result."""
    failures = 0
    for test_function in TESTS:
        name = test_function.__name__
        try:
            test_function()
        except Exception as error:
            failures += 1
            print(f"[FAIL] {name}: {error}")
        else:
            print(f"[PASS] {name}")

    print()
    if failures:
        print(f"{failures} of {len(TESTS)} tests failed.")
        return 1
    print(f"All {len(TESTS)} tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
