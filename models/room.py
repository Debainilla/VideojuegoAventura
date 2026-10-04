"""A single cell of the castle, and the three kinds it can be."""

from enum import Enum

from config import Config
from models.enemy import Enemy
from models.treasure import Treasure


class RoomType(Enum):
    """The three kinds of room the castle is built from.

    ``EMPTY`` covers both an untouched room and one whose treasure was
    taken or whose enemy left: once a room has been dealt with it goes
    back to ``EMPTY`` so the map never shows a solved room twice.
    """

    EMPTY = "empty"
    TREASURE = "treasure"
    ENEMY = "enemy"


class Room:
    """One square of the castle grid.

    A room knows where it sits in the grid (``row`` / ``column``), which
    other rooms it is connected to, and what it holds. It does **not**
    know where the player is, or how gold and damage are applied: that
    is the job of the :class:`~game.Game` engine.
    """

    def __init__(self, room_id, row, column):
        """Create an empty room at the given grid position."""
        self._id = room_id
        self._row = row
        self._column = column
        self._type = RoomType.EMPTY
        self._connections = []
        self._treasure = None
        self._enemy = None

    # --- Identity -------------------------------------------------

    @property
    def room_id(self):
        """Return the unique number that identifies this room."""
        return self._id

    @property
    def row(self):
        """Return the grid row this room sits in."""
        return self._row

    @property
    def column(self):
        """Return the grid column this room sits in."""
        return self._column

    @property
    def type(self):
        """Return the :class:`RoomType` of this room."""
        return self._type

    # --- Contents -------------------------------------------------

    @property
    def treasure(self):
        """Return the :class:`Treasure` here, or None."""
        return self._treasure

    @property
    def enemy(self):
        """Return the :class:`Enemy` here, or None."""
        return self._enemy

    def has_treasure(self):
        """Return True while the room still holds uncollected gold."""
        return self._treasure is not None

    def has_live_enemy(self):
        """Return True while an undefeated enemy is waiting here."""
        return self._enemy is not None and not self._enemy.is_defeated()

    def place_treasure(self):
        """Fill this room with a new random treasure."""
        self._treasure = Treasure.create_random()
        self._type = RoomType.TREASURE

    def place_enemy(self):
        """Put a new random enemy in this room."""
        self._enemy = Enemy.create_random()
        self._type = RoomType.ENEMY

    def remove_treasure(self):
        """Take the gold away and turn the room into an empty one."""
        self._treasure = None
        self._type = RoomType.EMPTY

    def remove_enemy(self):
        """Remove the enemy and turn the room into an empty one."""
        self._enemy = None
        self._type = RoomType.EMPTY

    def swap_contents_with(self, other):
        """Trade what this room and ``other`` hold.

        Both rooms keep their grid position and their passages; only
        the treasure and the enemy change hands. The type of each room
        is worked out again from whatever it now holds, so a swap can
        never leave a room showing the wrong kind.
        """
        self._treasure, other._treasure = other._treasure, self._treasure
        self._enemy, other._enemy = other._enemy, self._enemy
        self._refresh_type()
        other._refresh_type()

    def _refresh_type(self):
        """Set the type from what the room currently holds."""
        if self.has_live_enemy():
            self._type = RoomType.ENEMY
        elif self.has_treasure():
            self._type = RoomType.TREASURE
        else:
            self._type = RoomType.EMPTY

    # --- Connections ----------------------------------------------

    def connect_to(self, other_id):
        """Add a passage from this room to the room ``other_id``.

        Connections are stored on both ends by
        :meth:`Castle._build_maze`, so calling this once in each
        direction is the caller's job.
        """
        if other_id not in self._connections:
            self._connections.append(other_id)

    def is_adjacent_to(self, other_id):
        """Return True when there is a passage to ``other_id``.

        This is the check the engine uses to refuse illegal moves.
        """
        return other_id in self._connections

    @property
    def connections(self):
        """Return a copy of the list of connected room ids."""
        return list(self._connections)

    # --- Interface ------------------------------------------------

    @property
    def icon(self):
        """Return the Material Symbols icon that represents this room.

        Streamlit ships the Material Symbols font, so a
        ``":material/name:"`` string renders as a real icon.
        """
        if self.has_live_enemy():
            return Config.ICON_ENEMY
        if self.has_treasure():
            return Config.ICON_TREASURE
        return Config.ICON_EMPTY
