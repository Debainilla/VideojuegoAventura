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


def walled_castle():
    """Return a two-room castle: an empty start, then a wall.

    Room 1 touches room 0 in the grid but has no passage, which is the
    exact shape of the bump: side by side, not connected.
    """
    castle = Castle(1, 2)
    castle.get_room(1).place_wall()
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
    """Once found, the map icon always shows what the room holds.

    Every room here is discovered first: an unexplored room shows a
    question mark whatever it holds, which is the next test.
    """
    empty = Room(0, 0, 0)
    empty.discover()
    check("an empty room uses the empty icon",
          empty.icon == Config.ICON_EMPTY)

    treasure = Room(1, 0, 1)
    treasure.place_treasure()
    treasure.discover()
    check("a treasure room uses the treasure icon",
          treasure.icon == Config.ICON_TREASURE)

    enemy_room = Room(2, 0, 2)
    enemy_room.place_enemy()
    enemy_room.discover()
    check("an enemy room uses the enemy icon",
          enemy_room.icon == Config.ICON_ENEMY)
    enemy_room.remove_enemy()
    check("an emptied room goes back to the empty icon",
          enemy_room.icon == Config.ICON_EMPTY)

    wall = Room(3, 0, 3)
    wall.place_wall()
    wall.discover()
    check("a wall uses the wall icon", wall.icon == Config.ICON_WALL)


def test_fog_hides_what_an_unexplored_room_holds():
    """An unexplored room shows a question mark, not its contents."""
    check("a room starts unexplored", not Room(0, 0, 0).discovered)

    treasure = Room(1, 0, 1)
    treasure.place_treasure()
    check("fog hides a treasure", treasure.icon == Config.ICON_UNKNOWN)

    enemy_room = Room(2, 0, 2)
    enemy_room.place_enemy()
    check("fog hides an enemy", enemy_room.icon == Config.ICON_UNKNOWN)

    wall = Room(3, 0, 3)
    wall.place_wall()
    check("fog hides a wall", wall.icon == Config.ICON_UNKNOWN)

    treasure.discover()
    treasure.discover()
    check("discovering is idempotent and then reveals the truth",
          treasure.discovered and treasure.icon == Config.ICON_TREASURE)


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
    """Every walkable room can be walked to from the starting room.

    Walls are excluded: they hold no passages by design, so the maze
    spans the walkable rooms only.
    """
    unreachable = 0
    for _ in range(50):
        castle = Castle.generate_random()
        reached = castle.visited_count_from(Config.STARTING_ROOM)
        if reached != castle.walkable_room_count:
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
    """A maze of N walkable rooms has exactly N-1 passages."""
    castle = Castle.generate_random()
    passages = sum(
        len(room.connections) for room in castle.rooms
    ) // 2
    check("the maze has one passage less than walkable rooms",
          passages == castle.walkable_room_count - 1)


# --- Castle: walls -------------------------------------------------

def test_castle_has_exactly_the_configured_walls():
    """Every castle has exactly ``WALL_ROOMS`` walls, never the start."""
    wrong_count = 0
    start_is_wall = 0
    for _ in range(100):
        castle = Castle.generate_random()
        walls = castle.walls()
        if len(walls) != Config.WALL_ROOMS:
            wrong_count += 1
        if castle.get_room(Config.STARTING_ROOM).is_wall():
            start_is_wall += 1
    check("100 castles hold the configured number of walls",
          wrong_count == 0)
    check("the starting room is never a wall", start_is_wall == 0)


def test_walls_are_left_out_of_the_maze():
    """A wall has no passages and holds nothing at all."""
    leaks_passage = False
    holds_loot = False
    for _ in range(100):
        castle = Castle.generate_random()
        for wall_id in castle.walls():
            wall = castle.get_room(wall_id)
            if wall.connections:
                leaks_passage = True
            if wall.has_treasure() or wall.has_live_enemy():
                holds_loot = True
    check("no wall is wired into the maze", not leaks_passage)
    check("no wall holds treasure or an enemy", not holds_loot)


def test_every_wall_can_be_bumped_into():
    """No wall is walled in, and walls never cut the map in two.

    Both properties are what make walls fair. A ring of walls would
    strand a treasure the player could never reach, making the run
    unwinnable, and a wall surrounded only by other walls could never be
    discovered at all.
    """
    stranded = 0
    unreachable_wall = 0
    for _ in range(200):
        castle = Castle.generate_random()
        if castle.visited_count_from(Config.STARTING_ROOM) != \
                castle.walkable_room_count:
            stranded += 1
        for wall_id in castle.walls():
            touching = [
                other_id
                for other_id in castle.room_ids()
                if castle.is_side_by_side(wall_id, other_id)
                and not castle.get_room(other_id).is_wall()
            ]
            if not touching:
                unreachable_wall += 1
    check("walls never strand part of the castle", stranded == 0)
    check("every wall has a walkable neighbour", unreachable_wall == 0)


def test_walls_do_not_change_the_fixed_content_counts():
    """Walls take a room's place without eating a treasure or an enemy."""
    treasures = 0
    enemies = 0
    for _ in range(50):
        castle = Castle.generate_random()
        treasures += sum(
            1 for room in castle.rooms
            if room.type is RoomType.TREASURE
        )
        enemies += sum(
            1 for room in castle.rooms if room.type is RoomType.ENEMY
        )
    check("50 castles still hold 4 treasures each",
          treasures == 50 * Config.TREASURE_ROOMS)
    check("50 castles still hold 3 enemies each",
          enemies == 50 * Config.ENEMY_ROOMS)


def test_a_castle_with_walls_is_still_winnable():
    """The gold goal stays reachable even with walls in the way."""
    reachable_gold = 0
    for _ in range(200):
        castle = Castle.generate_random()
        reached = set()
        stack = [Config.STARTING_ROOM]
        while stack:
            for other in castle.neighbours_of(stack.pop()):
                if other not in reached:
                    reached.add(other)
                    stack.append(other)
        gold = sum(
            room.treasure.amount()
            for room in castle.rooms
            if room.room_id in reached and room.has_treasure()
        )
        if gold >= Config.GOLD_GOAL:
            reachable_gold += 1
    check("200 walled castles can still reach the gold goal",
          reachable_gold == 200)


# --- Game: movement ----------------------------------------------

def test_game_rejects_illegal_moves():
    """The engine refuses any move that is not a real passage."""
    game = Game.new_game()
    castle = game.castle
    here = castle.get_room(Config.STARTING_ROOM).room_id

    check("a room that does not exist is refused",
          "does not exist" in game.move_to(9999))

    # Picked by shape, not at random: a wall would be refused for a
    # different reason and would test nothing here.
    far_away = next(
        room_id
        for room_id in castle.room_ids()
        if not castle.is_side_by_side(here, room_id)
        and not castle.get_room(room_id).is_adjacent_to(here)
    )
    check("a room far away is refused",
          "no passage" in game.move_to(far_away))

    blocked_wall = next(
        (
            room_id
            for room_id in castle.room_ids()
            if castle.is_side_by_side(here, room_id)
            and not castle.get_room(room_id).is_wall()
            and not castle.get_room(room_id).is_adjacent_to(here)
        ),
        None,
    )
    if blocked_wall is not None:
        check("a side-by-side room with no passage is refused",
              "no passage" in game.move_to(blocked_wall))

    neighbour = castle.neighbours_of(here)[0]
    check("a real passage is allowed",
          "no passage" not in game.move_to(neighbour))
    check("the player really moved there",
          game.player.position == neighbour)


# --- Game: fog of war ---------------------------------------------

def test_a_run_starts_with_only_the_starting_room_found():
    """The castle opens under fog: one known room out of sixteen."""
    game = Game.new_game()
    castle = game.castle
    found = [room.room_id for room in castle.rooms if room.discovered]

    check("the starting room is visible at once",
          castle.get_room(Config.STARTING_ROOM).discovered)
    check("every other room is still hidden",
          found == [Config.STARTING_ROOM])
    check("the counter agrees", game.discovered_count == 1)


def test_walking_into_a_room_reveals_it():
    """Entering a room lifts the fog on that room only."""
    game = Game(treasure_castle(room_count=3))
    check("the next room starts hidden",
          not game.castle.get_room(1).discovered)

    game.move_to(1)
    check("entering reveals the room",
          game.castle.get_room(1).discovered)
    check("the room after it stays hidden",
          not game.castle.get_room(2).discovered)
    check("the counter went up by one", game.discovered_count == 2)


def test_fog_never_leaks_a_treasure():
    """No unexplored treasure shows its icon or its room as found."""
    leaked = 0
    for _ in range(50):
        game = Game.new_game()
        castle = game.castle
        for room in castle.rooms:
            if room.has_treasure() and (
                room.discovered
                or room.icon != Config.ICON_UNKNOWN
            ):
                leaked += 1
    check("no unexplored treasure leaks through the map", leaked == 0)


def test_the_log_opens_without_revealing_anything():
    """Nothing about the unexplored castle is in the log yet.

    Only the single welcome line is there: no room has been reported and
    no enemy named. (The welcome itself mentions gold, because it tells
    the player what the goal is.)
    """
    game = Game.new_game()
    joined = " ".join(game.log).lower()
    check("no room has been reported yet", "room" not in joined)
    check("no treasure has been reported yet", "you found" not in joined)
    check("no enemy has been named yet",
          not any(name.lower() in joined for name in Config.ENEMY_NAMES))


# --- Game: bumping into a wall ------------------------------------

def test_bumping_a_wall_keeps_the_player_in_place():
    """Walking into stone reveals it and costs nothing."""
    game = Game(walled_castle())
    health = game.player.health
    visited = game.rooms_visited

    check("the wall starts hidden", not game.castle.get_room(1).discovered)

    message = game.move_to(1)

    check("the message says it is a wall", "wall" in message.lower())
    check("the player did not move", game.player.position == 0)
    check("the wall is now discovered",
          game.castle.get_room(1).discovered)
    check("it does not count as a room entered",
          game.rooms_visited == visited)
    check("it costs no health", game.player.health == health)
    check("no fight was triggered", not game.in_combat)
    check("the walls-found counter went up", game.walls_found == 1)


def test_a_wall_can_be_bumped_into_again():
    """A wall already found says so again and still blocks the way."""
    game = Game(walled_castle())
    game.move_to(1)
    message = game.move_to(1)
    check("the same wall still stops the player",
          game.player.position == 0)
    check("and still reports itself as a wall",
          "wall" in message.lower())


def test_a_wall_far_away_is_not_a_bump():
    """Side by side is required: a distant wall is just unreachable."""
    castle = Castle(2, 2)
    castle.get_room(3).place_wall()  # not touching room 0
    game = Game(castle)
    message = game.move_to(3)
    check("a distant wall is not discovered",
          not castle.get_room(3).discovered)
    check("a distant wall is refused as unreachable",
          "no passage" in message)


def test_movement_is_blocked_by_a_wall_during_combat():
    """Combat still comes first, even with a wall to bump into."""
    castle = Castle(1, 3)
    join(castle, 0, 1)
    castle.get_room(1).place_enemy()
    castle.get_room(2).place_wall()
    game = Game(castle)
    game.move_to(1)

    message = game.move_to(2)
    check("the wall cannot be bumped during a fight",
          "Solve the problem" in message)
    check("and it stays hidden while the fight is on",
          not castle.get_room(2).discovered)


def test_player_can_walk_the_whole_maze():
    """Every walkable room really is reachable by playing normally."""
    game = Game.new_game()
    reached = game.castle.visited_count_from(game.player.position)
    check("the starting position reaches every walkable room",
          reached == game.castle.walkable_room_count)


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

def _discover_tests():
    """Return every test function in this file, in the order written.

    Discovered automatically on purpose. An explicit hand-written list
    silently skips any test that was added but not registered, and a
    suite that reports success while quietly skipping tests is worse
    than no suite at all.
    """
    return [
        value
        for name, value in list(globals().items())
        if name.startswith("test_") and callable(value)
    ]


TESTS = _discover_tests()


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
