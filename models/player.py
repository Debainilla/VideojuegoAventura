"""The adventurer who explores the castle."""

from config import Config


class Player:
    """Health, gold and position, plus the rules that change them.

    This class is intentionally small. It does not know what a castle
    or an enemy is: it only knows how to be hurt, how to get richer and
    how to walk to a room id.
    """

    def __init__(self, name):
        """Start the player at full health, with no gold, at the exit."""
        self._name = name
        self._health = Config.STARTING_HEALTH
        self._gold = 0
        self._position = Config.STARTING_ROOM

    @property
    def name(self):
        """Return the adventurer's name."""
        return self._name

    @property
    def health(self):
        """Return the health points left."""
        return self._health

    @property
    def gold(self):
        """Return the gold collected so far."""
        return self._gold

    @property
    def position(self):
        """Return the id of the room the player is standing in."""
        return self._position

    def take_damage(self, amount):
        """Lose ``amount`` health points, never going below zero.

        Clamping at zero here means every other class can safely ask
        "is the player alive?" without worrying about overshooting.
        """
        self._health = max(0, self._health - amount)

    def gain_gold(self, amount):
        """Add ``amount`` gold coins to the total."""
        self._gold += amount

    def move_to(self, room_id):
        """Teleport the player to ``room_id``.

        The caller is responsible for checking that the move is legal;
        see :meth:`game.Game.move_to`, which owns that rule.
        """
        self._position = room_id

    def is_alive(self):
        """Return True while the player still has health left."""
        return self._health > 0

    def has_enough_gold(self):
        """Return True once the gold goal has been reached."""
        return self._gold >= Config.GOLD_GOAL
