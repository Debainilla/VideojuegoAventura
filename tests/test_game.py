"""Tests for the game engine.

These run **without Streamlit**, which is the point: the game rules
live in plain Python classes, so they can be checked from a terminal.

Run them with::

    python -m tests.test_game

No testing framework is needed, only ``assert`` and a short runner. The
file prints one line per check and exits with a non-zero status if
anything fails.

Every test below uses the **public** API of the classes. Nothing here
touches a private attribute, so the tests double as a check that the
public interface is enough to play the whole game.
"""

import sys

from config import Config
from game import Game, GameState
from models.castle import Castle
from models.enemy import Enemy
from models.operation import MathOperation
from models.player import Player
from models.room import Room, RoomType
from models.treasure import Treasure

# --- Tiny test harness -------------------------------------------

_FAILURES = []


def check(description, condition):
    """Record whether ``condition`` held, and report it."""
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {description}")
    if not condition:
        _FAILURES.append(description)


# --- Helpers ------------------------------------------------------

def solve(operation):
    """Return the correct answer for a displayed problem.

    The answer is recomputed from the public ``text`` property instead
    of being read from the object, so this also proves the text is
    complete and parseable.
    """
    first, sign, second, _, _ = operation.text.split()
    first, second = int(first), int(second)
    if sign == "+":
        return str(first + second)
    if sign == "-":
        return str(first - second)
    return str(first * second)


def never_an_answer():
    """Return an answer that no problem in the game can ever match.

    Operands run from 2 to 9, so the largest possible result is
    9 x 9 = 81. Subtraction can answer with a negative number, so a
    plain negative value would not be safe; 1000 can never be right.
    """
    return "1000"


def find_rooms_of_type(castle, room_type):
    """Return the ids of every room of ``room_type``."""
    return [
        room.room_id
        for room in castle.rooms
        if room.type is room_type
    ]


def join(castle, first_id, second_id):
    """Dig a passage between two rooms, in both directions."""
    castle.get_room(first_id).connect_to(second_id)
    castle.get_room(second_id).connect_to(first_id)


def empty_castle(room_count=2):
    """Return a castle of connected empty rooms, and nothing else."""
    castle = Castle(1, room_count)
    for room_id in range(1, room_count):
        join(castle, room_id - 1, room_id)
    return castle


def duel_castle():
    """Return a two-room castle: an empty start, then one enemy.

    Random castles are fine for exploring the layout, but the combat
    rules are much easier to check against a layout we know exactly.
    """
    castle = Castle(1, 2)
    join(castle, 0, 1)
    castle.get_room(1).place_enemy()
    return castle


def treasure_castle(room_count=3):
    """Return a one-row castle whose rooms after the start all hold gold.

    With three treasures of 20 to 40 gold each, the total is always at
    least 60, so the gold goal is always reachable.
    """
    castle = Castle(1, room_count)
    for room_id in range(1, room_count):
        join(castle, room_id - 1, room_id)
        castle.get_room(room_id).place_treasure()
    return castle


def meet_enemy():
    """Return a game with the player already facing an enemy."""
    game = Game(duel_castle())
    game.move_to(1)
    return game, game.current_room().enemy


# --- MathOperation ------------------------------------------------

def test_operation_text():
    """A random operation is displayed as '7 + 8 = ?'."""
    for _ in range(200):
        operation = MathOperation.create_random()
        parts = operation.text.split()
        if not (
            len(parts) == 5
            and parts[0].isdigit()
            and parts[1] in Config.OPERATORS
            and parts[2].isdigit()
            and parts[3] == "="
            and parts[4] == "?"
        ):
            check("operation text has the 'a op b = ?' shape", False)
            return
    check("200 operation texts have the 'a op b = ?' shape", True)


def test_subtraction_is_never_negative():
    """Subtraction asks for a positive answer every time."""
    all_positive = True
    for _ in range(1000):
        operation = MathOperation.create_random()
        if int(solve(operation)) < 0:
            all_positive = False
            break
    check("1000 operations never ask for a negative result",
          all_positive)


def test_operation_answers():
    """Only the exact integer counts as the correct answer."""
    operation = MathOperation(7, 8, "+", 15)
    check("the correct answer is accepted", operation.is_correct("15"))
    check("stray spaces are tolerated", operation.is_correct("  15 "))
    check("a wrong number is rejected", not operation.is_correct("14"))
    check("an empty answer is rejected", not operation.is_correct(""))
    check("a written answer is rejected",
          not operation.is_correct("fifteen"))
    check("a decimal answer is rejected",
          not operation.is_correct("15.0"))


def test_operation_result_matches_the_text():
    """Solving the displayed text really does pass the operation.

    The result is deliberately not read back from the object: the test
    rebuilds the answer from the text the player would see, then asks
    the operation whether that answer is right. That proves the shown
    problem and the hidden result cannot drift apart.
    """
    mismatches = 0
    for _ in range(300):
        operation = MathOperation.create_random()
        if not operation.is_correct(solve(operation)):
            mismatches += 1
    check("300 solved problems match the text shown to the player",
          mismatches == 0)


# --- Treasure -----------------------------------------------------

def test_treasure():
    """Every treasure is worth between the configured limits."""
    amounts = [Treasure.create_random().amount() for _ in range(500)]
    check("treasure gold stays inside the configured range",
          all(Config.TREASURE_GOLD_MIN <= amount <= Config.TREASURE_GOLD_MAX
              for amount in amounts))


# --- Enemy --------------------------------------------------------

def test_enemy():
    """An enemy asks a fresh problem every time and can be beaten."""
    enemy = Enemy.create_random()
    check("a new enemy starts undefeated", not enemy.is_defeated())
    check("a new enemy has not asked anything yet",
          enemy.question is None)

    first = enemy.pose_question()
    check("posing a question stores it on the enemy",
          first is enemy.question)

    second = enemy.pose_question()
    check("asking again replaces the problem",
          second is not first)
    check("and the new problem is the one on show",
          second is enemy.question)

    enemy.defeat()
    check("a defeated enemy reports it", enemy.is_defeated())


# --- Player -------------------------------------------------------

def test_player():
    """Health, gold and position follow the simple rules."""
    player = Player("Tester")
    check("the player starts at full health",
          player.health == Config.STARTING_HEALTH)
    check("the player starts with no gold", player.gold == 0)
    check("the player starts in the starting room",
          player.position == Config.STARTING_ROOM)
    check("the player starts alive", player.is_alive())

    player.take_damage(3)
    check("damage reduces health", player.health == 17)

    player.take_damage(999)
    check("health never drops below zero", player.health == 0)
    check("a player at 0 health is not alive", not player.is_alive())

    player.gain_gold(25)
    check("gold is added up", player.gold == 25)
    check("25 gold is not enough to win", not player.has_enough_gold())
    player.gain_gold(Config.GOLD_GOAL)
    check("reaching the goal counts as enough gold",
          player.has_enough_gold())


# --- Room ---------------------------------------------------------

def test_room_starts_empty():
    """A new room is empty and knows where it sits."""
    room = Room(7, 1, 2)
    check("a new room is empty", room.type is RoomType.EMPTY)
    check("a new room has no treasure", not room.has_treasure())
    check("a new room has no enemy", not room.has_live_enemy())
    check("a new room is connected to nothing", room.connections == [])
    check("a room knows its id", room.room_id == 7)
    check("a room knows its grid position",
          (room.row, room.column) == (1, 2))


def test_room_contents_appear_and_disappear():
    """Placing and removing contents keeps the type honest."""
    room = Room(0, 0, 0)

    room.place_treasure()
    check("a treasure makes the room a treasure room",
          room.type is RoomType.TREASURE)
    check("the treasure is there", room.has_treasure())
    room.remove_treasure()
    check("taking it leaves an empty room",
          room.type is RoomType.EMPTY)
    check("and no treasure behind", not room.has_treasure())

    room.place_enemy()
    check("an enemy makes the room an enemy room",
          room.type is RoomType.ENEMY)
    check("the enemy is there", room.has_live_enemy())
    room.remove_enemy()
    check("removing it leaves an empty room",
          room.type is RoomType.EMPTY)
    check("and no enemy behind", not room.has_live_enemy())


def test_room_icon_follows_the_contents():
    """The map icon always shows what the room really holds."""
    empty = Room(0, 0, 0)
    check("an empty room uses the empty icon",
          empty.icon == Config.ICON_EMPTY)

    treasure = Room(1, 0, 1)
    treasure.place_treasure()
    check("a treasure room uses the treasure icon",
          treasure.icon == Config.ICON_TREASURE)

    enemy_room = Room(2, 0, 2)
    enemy_room.place_enemy()
    check("an enemy room uses the enemy icon",
          enemy_room.icon == Config.ICON_ENEMY)
    enemy_room.remove_enemy()
    check("an emptied room goes back to the empty icon",
          enemy_room.icon == Config.ICON_EMPTY)


def test_room_connections_are_symmetric():
    """Passages are stored on both ends, and never twice."""
    left = Room(0, 0, 0)
    right = Room(1, 0, 1)

    left.connect_to(1)
    right.connect_to(0)
    left.connect_to(1)
    check("the passage exists from the left", left.is_adjacent_to(1))
    check("and from the right", right.is_adjacent_to(0))
    check("a passage is only stored once",
          left.connections == [1] and right.connections == [0])


def test_room_swaps_what_it_holds():
    """Trading contents keeps both rooms' types correct."""
    treasure = Room(0, 0, 0)
    treasure.place_treasure()
    amount = treasure.treasure.amount()
    plain = Room(1, 0, 1)

    treasure.swap_contents_with(plain)

    check("the treasure moved to the other room",
          plain.has_treasure() and plain.treasure.amount() == amount)
    check("and it is now a treasure room",
          plain.type is RoomType.TREASURE)
    check("the room that gave it away is empty now",
          treasure.type is RoomType.EMPTY)
    check("and it kept its own id",
          (treasure.room_id, plain.room_id) == (0, 1))


# --- Castle: size and contents ------------------------------------

def test_castle_shape():
    """The grid has the size and the room ids it should."""
    castle = Castle.generate_random()
    expected = Config.MAP_ROWS * Config.MAP_COLUMNS
    check("the castle has rows x columns rooms",
          castle.room_count == expected)
    check("room ids cover the whole grid with no gaps",
          castle.room_ids() == list(range(expected)))
    check("the starting room holds no treasure",
          not castle.get_room(Config.STARTING_ROOM).has_treasure())
    check("the starting room holds no enemy",
          not castle.get_room(Config.STARTING_ROOM).has_live_enemy())


def test_castle_contents():
    """The dealt rooms are exactly as many as the rules promise."""
    castle = Castle.generate_random()
    treasures = find_rooms_of_type(castle, RoomType.TREASURE)
    enemies = find_rooms_of_type(castle, RoomType.ENEMY)

    check("there are exactly the promised treasure rooms",
          len(treasures) == Config.TREASURE_ROOMS)
    check("there are exactly the promised enemy rooms",
          len(enemies) == Config.ENEMY_ROOMS)
    check("the player can beat the gold goal with the treasures",
          len(treasures) * Config.TREASURE_GOLD_MIN >= Config.GOLD_GOAL)
    # A single enemy is enough to kill, because it stays in the room
    # and asks again after every wrong answer. That is what makes the
    # game tense, and it is why the health and damage values matter.
    hits_to_die = (
        Config.STARTING_HEALTH + Config.ENEMY_DAMAGE - 1
    ) // Config.ENEMY_DAMAGE
    check("one enemy can kill the player over several answers",
          hits_to_die > len(enemies))
    check("every treasure pile is worth a fair amount",
          all(
              Config.TREASURE_GOLD_MIN
              <= castle.get_room(room_id).treasure.amount()
              <= Config.TREASURE_GOLD_MAX
              for room_id in treasures
          ))


def test_starting_room_is_emptied_without_losing_content():
    """The start is safe, and the swap keeps the fixed counts.

    Making room 0 safe by throwing its contents away would leave the
    castle short of a treasure or an enemy, so the contents are traded
    with an empty room instead. This is run many times because the
    shuffled deal only puts something in room 0 now and then.
    """
    for _ in range(60):
        castle = Castle.generate_random()
        start = castle.get_room(Config.STARTING_ROOM)
        if not check("the starting room is empty",
                     start.type is RoomType.EMPTY):
            return
        check("and the counts still add up",
              len(find_rooms_of_type(castle, RoomType.TREASURE))
              == Config.TREASURE_ROOMS
              and len(find_rooms_of_type(castle, RoomType.ENEMY))
              == Config.ENEMY_ROOMS)
        check("and only the three room types are used",
              {room.type for room in castle.rooms}
              <= set(RoomType))


def test_castle_is_fully_connected():
    """Every room can be walked to from the starting room."""
    unreachable = 0
    for _ in range(50):
        castle = Castle.generate_random()
        reached = castle.visited_count_from(Config.STARTING_ROOM)
        if reached != castle.room_count:
            unreachable += 1
    check("50 generated castles are fully reachable", unreachable == 0)


def test_castle_connections_are_valid():
    """Passages are symmetric and only join side-by-side rooms."""
    castle = Castle.generate_random()
    valid = True
    for room in castle.rooms:
        for neighbour_id in room.connections:
            other = castle.get_room(neighbour_id)
            if not other.is_adjacent_to(room.room_id):
                valid = False  # not symmetric
            distance = abs(other.row - room.row) + abs(
                other.column - room.column
            )
            if distance != 1:
                valid = False  # not side by side
    check("every passage is symmetric and joins neighbouring cells",
          valid)


def test_castle_is_a_tree():
    """A maze of N rooms has exactly N-1 passages."""
    castle = Castle.generate_random()
    passages = sum(
        len(room.connections) for room in castle.rooms
    ) // 2
    check("the maze has one passage less than rooms",
          passages == castle.room_count - 1)


# --- Game: movement ----------------------------------------------

def test_game_rejects_illegal_moves():
    """The engine refuses any move that is not a real passage."""
    game = Game.new_game()
    castle = game.castle
    here = castle.get_room(Config.STARTING_ROOM).room_id

    check("a room that does not exist is refused",
          "does not exist" in game.move_to(9999))

    far_away = next(
        room_id
        for room_id in castle.room_ids()
        if not castle.get_room(room_id).is_adjacent_to(here)
    )
    check("a room with no passage is refused",
          "no passage" in game.move_to(far_away))

    neighbour = castle.neighbours_of(here)[0]
    check("a real passage is allowed",
          "no passage" not in game.move_to(neighbour))
    check("the player really moved there",
          game.player.position == neighbour)


def test_player_can_walk_the_whole_maze():
    """Every room really is reachable by playing normally."""
    game = Game.new_game()
    reached = game.castle.visited_count_from(game.player.position)
    check("the starting position reaches every room",
          reached == game.castle.room_count)


# --- Game: treasure ----------------------------------------------

def test_treasure_is_collected_once():
    """A treasure pays out on entry, and never a second time."""
    game = Game(treasure_castle(room_count=2))
    pile = game.castle.get_room(1).treasure.amount()

    game.move_to(1)
    check("entering a treasure room pays its gold",
          game.player.gold == pile)
    check("the player is standing in the treasure room",
          game.player.position == 1)
    check("the treasure room is empty afterwards",
          not game.current_room().has_treasure())

    # Step out and come back: there must be nothing left to find.
    game.move_to(0)
    gold_before = game.player.gold
    message = game.move_to(1)
    check("a second visit pays no gold",
          game.player.gold == gold_before)
    check("a second visit reports an empty room", "empty" in message)


def test_room_with_nothing_says_so():
    """An empty room costs nothing and says it is empty."""
    game = Game(empty_castle())
    health_before = game.player.health
    gold_before = game.player.gold

    message = game.move_to(0)
    check("staying put is refused", "no passage" in message)

    message = game.move_to(1)
    check("an empty room is reported as empty", "empty" in message)
    check("an empty room costs no health",
          game.player.health == health_before)
    check("an empty room pays no gold", game.player.gold == gold_before)


# --- Game: combat -------------------------------------------------

def test_entering_an_enemy_room_starts_a_fight():
    """An enemy room poses a problem and starts the clock."""
    game, enemy = meet_enemy()
    check("entering an enemy room starts combat", game.in_combat)
    check("the enemy has asked a problem", enemy.question is not None)
    check("the clock is running", game.time_remaining() > 0)
    check("the player is told what to solve",
          enemy.question.text in game.log[-1])
    check("the player cannot move away", not game.can_move())


def test_wrong_answer_costs_health_and_a_new_problem():
    """A wrong answer hurts, and the enemy asks something new."""
    game, enemy = meet_enemy()
    first_question = enemy.question
    health_before = game.player.health

    game.submit_answer(never_an_answer())

    check("a wrong answer costs health",
          game.player.health == health_before - Config.ENEMY_DAMAGE)
    check("the fight goes on", game.in_combat)
    check("the enemy asks a different problem",
          enemy.question is not first_question)
    check("the clock restarts", game.time_remaining() > 0)
    check("the player cannot move away", not game.can_move())


def test_correct_answer_defeats_the_enemy():
    """Solving the problem clears the room and pays a reward."""
    game, enemy = meet_enemy()
    gold_before = game.player.gold
    health_before = game.player.health

    message = game.submit_answer(solve(enemy.question))

    check("the enemy is defeated", enemy.is_defeated())
    check("the room is empty afterwards",
          not game.current_room().has_live_enemy())
    check("combat is over", not game.in_combat)
    check("beating an enemy pays gold",
          game.player.gold == gold_before + Config.GOLD_PER_ENEMY)
    check("solving a problem costs no health",
          game.player.health == health_before)
    check("the player can move again", game.can_move())
    check("the message names the enemy", enemy.name in message)


def test_no_combat_without_an_enemy():
    """Answering in an empty room does nothing."""
    game = Game(treasure_castle(room_count=2))
    health_before = game.player.health
    message = game.submit_answer("42")
    check("answering outside combat is refused",
          "no enemy" in message)
    check("and costs no health", game.player.health == health_before)


def test_timeout_costs_health_and_the_enemy_flees():
    """Running out of time hurts, and the enemy leaves the room."""
    game, enemy = meet_enemy()
    health_before = game.player.health

    message = game.register_timeout()

    check("a timeout costs health",
          game.player.health == health_before - Config.ENEMY_DAMAGE)
    check("the enemy flees on timeout",
          not game.current_room().has_live_enemy())
    check("a fleeing enemy is not counted as beaten",
          not enemy.is_defeated())
    check("combat ends on timeout", not game.in_combat)
    check("the timeout is reported", "Time ran out" in message)
    check("the clock is stopped", game.time_remaining() == 0.0)
    check("the player can move again", game.can_move())


def test_timeout_is_a_no_op_outside_combat():
    """The timeout penalty only applies during a fight."""
    game = Game(duel_castle())
    health_before = game.player.health
    game.register_timeout()
    check("no damage outside combat", game.player.health == health_before)
    check("and the run carries on", game.state is GameState.PLAYING)


def test_movement_is_blocked_during_combat():
    """The player cannot walk away from an enemy."""
    game, _ = meet_enemy()

    message = game.move_to(0)
    check("moving during combat is refused", "Solve" in message)
    check("the player did not move", game.player.position == 1)


# --- Game: end of the run ----------------------------------------

def test_running_out_of_health_is_a_defeat():
    """Four wrong answers in the same room end the run."""
    game, _ = meet_enemy()

    wrong_answers = 0
    while game.state is GameState.PLAYING and wrong_answers < 10:
        game.submit_answer(never_an_answer())
        wrong_answers += 1

    check("the run ends before the answers run out",
          game.state is GameState.DEFEAT)
    check("four wrong answers were needed", wrong_answers == 4)
    check("the player is out of health", not game.player.is_alive())
    check("combat is stopped on death", not game.in_combat)
    check("the player cannot move after dying", not game.can_move())
    check("moving after death is refused", "over" in game.move_to(0))


def test_reaching_the_gold_goal_is_a_victory():
    """Collecting the treasure wins the run."""
    game = Game(treasure_castle(room_count=4))

    check("a fresh run is playing", game.state is GameState.PLAYING)
    for room_id in (1, 2, 3):
        if game.state is GameState.PLAYING:
            game.move_to(room_id)

    check("the gold goal is reached",
          game.player.gold >= Config.GOLD_GOAL)
    check("the state becomes VICTORY", game.state is GameState.VICTORY)
    check("no fight was left unfinished", not game.in_combat)
    check("the player cannot move after winning", not game.can_move())
    check("moving after winning is refused", "over" in game.move_to(0))


def test_ten_plays_can_be_created():
    """A quick smoke test that generation never crashes."""
    healthy = True
    for _ in range(10):
        game = Game.new_game()
        healthy = healthy and game.castle.room_count > 0
        healthy = healthy and game.state is GameState.PLAYING
        healthy = healthy and game.can_move()
    check("ten fresh plays are ready to go", healthy)


# --- Runner -------------------------------------------------------

TESTS = [
    test_operation_text,
    test_subtraction_is_never_negative,
    test_operation_answers,
    test_operation_result_matches_the_text,
    test_treasure,
    test_enemy,
    test_player,
    test_room_starts_empty,
    test_room_contents_appear_and_disappear,
    test_room_icon_follows_the_contents,
    test_room_connections_are_symmetric,
    test_room_swaps_what_it_holds,
    test_castle_shape,
    test_castle_contents,
    test_starting_room_is_emptied_without_losing_content,
    test_castle_is_fully_connected,
    test_castle_connections_are_valid,
    test_castle_is_a_tree,
    test_game_rejects_illegal_moves,
    test_player_can_walk_the_whole_maze,
    test_treasure_is_collected_once,
    test_room_with_nothing_says_so,
    test_entering_an_enemy_room_starts_a_fight,
    test_wrong_answer_costs_health_and_a_new_problem,
    test_correct_answer_defeats_the_enemy,
    test_no_combat_without_an_enemy,
    test_timeout_costs_health_and_the_enemy_flees,
    test_timeout_is_a_no_op_outside_combat,
    test_movement_is_blocked_during_combat,
    test_running_out_of_health_is_a_defeat,
    test_reaching_the_gold_goal_is_a_victory,
    test_ten_plays_can_be_created,
]


def main():
    """Run every test and report the result."""
    for test in TESTS:
        print(f"\n--- {test.__name__} " + "-" * 30)
        test()

    print("\n" + "=" * 62)
    if _FAILURES:
        print(f"{len(_FAILURES)} CHECK(S) FAILED:")
        for failure in _FAILURES:
            print(f"  - {failure}")
        return 1
    print(f"All checks passed ({len(TESTS)} test groups).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
