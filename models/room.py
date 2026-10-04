"""A single cell of the castle, and the four kinds it can be."""

from enum import Enum

from config import Config
from models.enemy import Enemy
from models.treasure import Treasure


class RoomType(Enum):
    """The four kinds of room the castle is built from.

    ``EMPTY`` covers both an untouched room and one whose treasure was
    taken or whose enemy left: once a room has been dealt with it goes
    back to ``EMPTY`` so the map never shows a solved room twice.

    ``WALL`` is different from ``EMPTY``: it is not "nothing here" but
    "solid stone here". A wall room can never be entered, it is left out
    of the maze, and it holds neither treasure nor enemy.
    """

    EMPTY = "empty"
    TREASURE = "treasure"
    ENEMY = "enemy"
    WALL = "wall"


class Room:
    """One square of the castle grid.

    A room knows where it sits in the grid (``row`` / ``column``), which
    other rooms it is connected to, and what it holds. It does **not**
    know where the player is, or how gold and damage are applied: that
    is the job of the :class:`~game.Game` engine.
    """

    def __init__(self, room_id, row, column):
        """Create an empty, unexplored room at the given grid position.

        ``_discovered`` starts False: this is the fog of war. A room only
        becomes visible once the player walks into it or bumps into it.
        """
        self._id = room_id
        self._row = row
        self._column = column
        self._type = RoomType.EMPTY
        self._connections = []
        self._treasure = None
        self._enemy = None
        self._discovered = False

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

    def place_wall(self):
        """Turn this room into solid stone.

        Called before the maze is built, so the wall is already standing
        when the depth-first search picks its passages, which is what
        keeps it out of the maze.
        """
        self._treasure = None
        self._enemy = None
        self._type = RoomType.WALL

    def place_empty(self):
        """Strip this room back to bare, walkable floor.

        The undo for :meth:`place_wall`: the castle generator raises a
        candidate wall, checks it did not cut the map in two, and puts
        the room back if it did.
        """
        self._treasure = None
        self._enemy = None
        self._type = RoomType.EMPTY

    def is_wall(self):
        """Return True when this room is a solid wall.

        A wall can never be entered, no matter what the passages say.
        """
        return self._type is RoomType.WALL

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
        """Set the type from what the room currently holds.

        A wall stays a wall: it is stone, not a container, so working
        the type out from its contents must never overwrite it.
        """
        if self.is_wall():
            return
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

        This is the check the engine uses to decide whether a move
        actually takes the player somewhere.
        """
        return other_id in self._connections

    def is_side_by_side(self, other):
        """Return True when ``other`` is a grid neighbour of this room.

        This is a *weaker* question than :meth:`is_adjacent_to`: it only
        asks whether the two cells touch, not whether a passage joins
        them. The difference is what makes walls work:

        * a passage neighbour  -> the player walks in;
        * a side-by-side wall  -> the player bumps into it and stays put;
        * side by side, no passage, not a wall -> a solid castle wall
          between two rooms, and there is nothing to discover.

        It takes a :class:`Room` rather than an id on purpose: turning
        ``room_id`` back into a ``(row, column)`` pair needs to know how
        many columns the grid has, and only the castle knows that.

        Kept separate from ``is_adjacent_to`` on purpose. Folding the two
        together would quietly turn every plain castle wall into a room
        the player could walk into.
        """
        return (abs(self._row - other.row)
                + abs(self._column - other.column)) == 1

    @property
    def connections(self):
        """Return a copy of the list of connected room ids."""
        return list(self._connections)

    # --- Fog of war -----------------------------------------------

    @property
    def discovered(self):
        """Return True once the player has found this room."""
        return self._discovered

    def discover(self):
        """Reveal this room. Doing it twice changes nothing."""
        self._discovered = True

    # --- Interface ------------------------------------------------

    @property
    def icon(self):
        """Return the Material Symbols icon that represents this room.

        Streamlit ships the Material Symbols font, so a
        ``":material/name:"`` string renders as a real icon.

        Fog of war comes first: an unexplored room shows a question mark
        whatever it holds, so the icon can never leak a treasure or an
        enemy the player has not met yet.
        """
        if not self._discovered:
            return Config.ICON_UNKNOWN
        if self.is_wall():
            return Config.ICON_WALL
        if self.has_live_enemy():
            return Config.ICON_ENEMY
        if self.has_treasure():
            return Config.ICON_TREASURE
        return Config.ICON_EMPTY
