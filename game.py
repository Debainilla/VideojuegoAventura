"""The game engine: every rule of the game lives in this file.

:class:`Game` wires the :class:`~models.player.Player` to the
:class:`~models.castle.Castle`, decides what happens in each room, and
keeps the clock that the maths problems run on.

Nothing here imports Streamlit and nothing here prints. Every public
method returns a plain string, which is what makes the whole game
testable from the console with ``python -m tests.test_game``.
"""

import time
from enum import Enum

from config import Config
from models.castle import Castle
from models.player import Player


class GameState(Enum):
    """The three states a run can be in."""

    PLAYING = "playing"
    VICTORY = "victory"
    DEFEAT = "defeat"


class Game:
    """One run of the castle adventure.

    A single instance of this class *is* the game. The Streamlit
    interface keeps exactly one in ``st.session_state`` so the run
    survives the script reruns that happen on every click.
    """

    def __init__(self, castle=None):
        """Create a game, generating a random castle by default.

        ``castle`` may be passed to play on a specific layout. Nothing
        in the game needs it, but it lets the tests build a known
        castle and check the rules against it.
        """
        self._player = Player(Config.PLAYER_NAME)
        self._castle = castle if castle is not None \
            else Castle.generate_random()
        self._state = GameState.PLAYING
        self._in_combat = False
        self._deadline = 0.0
        self._log = ["Welcome to the castle! Find the gold and stay alive."]
        self._rooms_visited = 1
        self._enemies_defeated = 0
        # You can always see the room you are standing in, so the run
        # never opens on a question mark.
        self._castle.get_room(Config.STARTING_ROOM).discover()

    @staticmethod
    def new_game():
        """Return a fresh game, ready to be played."""
        return Game()

    # --- Read-only views for the interface ------------------------

    @property
    def player(self):
        """Return the :class:`Player` object."""
        return self._player

    @property
    def castle(self):
        """Return the :class:`Castle` object."""
        return self._castle

    @property
    def state(self):
        """Return the current :class:`GameState`."""
        return self._state

    @property
    def in_combat(self):
        """Return True while a maths problem is waiting to be solved."""
        return self._in_combat

    @property
    def log(self):
        """Return a copy of the adventure log, oldest line first."""
        return list(self._log)

    @property
    def rooms_visited(self):
        """Return how many rooms the player has entered."""
        return self._rooms_visited

    @property
    def discovered_count(self):
        """Return how many rooms the player has found so far.

        Counts rooms found by walking into them *and* rooms found by
        bumping into a wall, which is how exploration progress is shown
        in the interface.
        """
        return sum(
            1 for room in self._castle.rooms if room.discovered
        )

    @property
    def walls_found(self):
        """Return how many wall rooms the player has bumped into."""
        return sum(
            1 for room in self._castle.rooms
            if room.is_wall() and room.discovered
        )

    @property
    def enemies_defeated(self):
        """Return how many enemies the player has beaten."""
        return self._enemies_defeated

    def current_room(self):
        """Return the room the player is standing in."""
        return self._castle.get_room(self._player.position)

    def can_move(self):
        """Return True when the player is allowed to walk to a room."""
        return self._state is GameState.PLAYING and not self._in_combat

    def time_remaining(self):
        """Return the seconds left before the current answer times out.

        The remaining time is always *subtracted* from an absolute
        deadline rather than counted down, so the value stays correct
        even if the interface is slow to refresh it.
        """
        if not self._in_combat:
            return 0.0
        return max(0.0, self._deadline - time.time())

    # --- Movement -------------------------------------------------

    def move_to(self, room_id):
        """Try to walk into ``room_id`` and return a message.

        Three outcomes, in the order they are checked:

        * a passage leads there: the player moves in and the room is
          revealed;
        * it is a wall: the player stays exactly where they are and the
          wall is revealed instead;
        * anything else: refused.

        The wall case is checked *before* the passage test, so a wall is
        unwalkable even if the maze were ever to hand it a passage.
        Those guards are the safety net that stops the player leaving
        the castle. The interface already disables impossible buttons,
        but a rule enforced in only one place is a rule that can be
        bypassed.
        """
        if self._state is not GameState.PLAYING:
            return "The run is already over."

        if self._in_combat:
            return "Solve the problem before moving on."

        if not self._castle.has_room(room_id):
            return "That room does not exist."

        target = self._castle.get_room(room_id)
        current = self.current_room()

        if (target.is_wall()
                and self._castle.is_side_by_side(current.room_id, room_id)):
            return self._bump_into_wall(target)

        if not current.is_adjacent_to(room_id):
            return "There is no passage that way."

        self._player.move_to(room_id)
        self._rooms_visited += 1
        target.discover()
        return self._resolve_room()

    def _bump_into_wall(self, wall):
        """Walk into ``wall``, fail, and reveal it. Returns a message.

        Nothing else happens: the player does not move, the room does
        not count as visited, and no health is lost. Bumping into stone
        is how a wall gets discovered.
        """
        wall.discover()
        message = (
            f"Room {wall.room_id} is a solid wall. You cannot go "
            f"past it, but now you know it is there."
        )
        self._log_message(message)
        return message

    # --- What happens when you enter a room -----------------------

    def _resolve_room(self):
        """Apply the contents of the current room and return a message.

        An enemy takes priority over treasure. A room can only hold one
        of the two, but checking in this order keeps the code safe if
        that ever changes.
        """
        room = self.current_room()

        if room.has_live_enemy():
            return self._start_combat(room.enemy)

        if room.has_treasure():
            gold = room.treasure.amount()
            self._player.gain_gold(gold)
            # The gold is gone for good, so the room turns empty.
            room.remove_treasure()
            message = f"You found {gold} gold!"
            self._log_message(f"Room {room.room_id}: found {gold} gold.")
            self._check_victory()
            return message

        # Logged like every other outcome, so the adventure log tells
        # the whole story and not only the interesting parts.
        message = "The room is empty. Just dust and echoes."
        self._log_message(message)
        return message

    # --- Combat ---------------------------------------------------

    def _start_combat(self, enemy):
        """Pose the first problem of a fight and start the clock."""
        self._in_combat = True
        enemy.pose_question()
        self._deadline = time.time() + Config.ANSWER_TIME_LIMIT
        message = (
            f"{enemy.name} blocks the way! Solve: {enemy.question.text}"
        )
        self._log_message(message)
        return message

    def submit_answer(self, answer):
        """Answer the current problem and return a message.

        A correct answer defeats the enemy and earns gold. A wrong one
        costs health and the enemy asks a brand new problem, so a
        mistake costs health but never wastes the room.
        """
        if not self._in_combat:
            return "There is no enemy to answer here."

        # Answering on the buzzer counts as running out of time, so a
        # lucky click cannot sneak past the clock.
        if self.time_remaining() <= 0:
            return self.register_timeout()

        room = self.current_room()
        enemy = room.enemy

        if enemy.question.is_correct(answer):
            return self._defeat_enemy(enemy)

        self._player.take_damage(enemy.damage)
        self._log_message(
            f"Wrong answer: {enemy.damage} damage from {enemy.name}."
        )

        if not self._player.is_alive():
            self._state = GameState.DEFEAT
            self._in_combat = False
            self._deadline = 0.0
            self._log_message("Your health reached 0. You died.")
            return "Your health reached 0. You died."

        # The enemy stays and asks something new, with a new clock.
        enemy.pose_question()
        self._deadline = time.time() + Config.ANSWER_TIME_LIMIT
        message = f"Careful! Try again: {enemy.question.text}"
        self._log_message(message)
        return message

    def _defeat_enemy(self, enemy):
        """Beat ``enemy``, hand out the reward and free the room."""
        enemy.defeat()
        self._enemies_defeated += 1
        self._player.gain_gold(Config.GOLD_PER_ENEMY)
        self.current_room().remove_enemy()
        self._in_combat = False
        self._deadline = 0.0
        self._log_message(
            f"Defeated {enemy.name} for {Config.GOLD_PER_ENEMY} gold."
        )
        self._check_victory()
        reward = Config.GOLD_PER_ENEMY
        return f"You defeated the {enemy.name}! +{reward} gold"

    def register_timeout(self):
        """Apply the timeout penalty and return a message.

        On timeout the player loses health and **the enemy flees**,
        leaving the room empty. Letting the enemy stay and ask again
        would kill an absent player over and over with no way to
        react, so fleeing keeps the punishment real while making it
        impossible for the run to lock up.
        """
        if not self._in_combat:
            return ""

        room = self.current_room()
        enemy = room.enemy
        self._player.take_damage(enemy.damage)
        room.remove_enemy()
        self._in_combat = False
        self._deadline = 0.0

        if not self._player.is_alive():
            self._state = GameState.DEFEAT
            message = "Time ran out and your health reached 0. You died."
            self._log_message(message)
            return message

        message = (
            f"Time ran out! {enemy.name} hits you for {enemy.damage} "
            "and flees."
        )
        self._log_message(message)
        return message

    # --- End of the run -------------------------------------------

    def _check_victory(self):
        """Switch to the victory state once the gold goal is reached."""
        if (
            self._player.has_enough_gold()
            and self._state is GameState.PLAYING
        ):
            self._state = GameState.VICTORY
            self._in_combat = False
            self._log_message(
                f"You gathered {self._player.gold} gold. The castle "
                "is yours!"
            )

    # --- Adventure log --------------------------------------------

    def _log_message(self, message):
        """Append a line to the log, keeping it a bounded size."""
        self._log.append(message)
        if len(self._log) > Config.MAX_LOG_ENTRIES:
            # Drop the oldest line instead of letting the list grow
            # without limit during a long run.
            del self._log[0]
