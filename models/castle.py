"""The castle: it owns every room and knows how they are joined."""

import random

from config import Config
from models.room import Room, RoomType


class Castle:
    """A grid of rooms, wired together as a random maze.

    The castle is the *owner* of its rooms (a composition relationship
    in the UML diagram): it creates them, stores them, and looks them
    up. A room id is simply ``row * MAP_COLUMNS + column``, so looking a
    room up in the dictionary is instant.

    Some rooms are walls. They sit in the grid like any other room, but
    they hold no passages, so the maze is a tree over the walkable rooms
    only and every wall is reached by bumping into it from a neighbour.
    """

    def __init__(self, rows, columns):
        """Create a grid of ``rows`` x ``columns`` empty, unconnected
        rooms.

        Building the rooms here means a castle is valid the moment it
        exists: ``generate_random`` only has to add the passages and
        the contents, and the tests can build small layouts by hand.
        """
        self._rows = rows
        self._columns = columns
        self._rooms = {}
        for row in range(rows):
            for column in range(columns):
                room_id = self.id_at(row, column)
                self._rooms[room_id] = Room(room_id, row, column)

    # --- Grid shape -----------------------------------------------

    @property
    def rows(self):
        """Return how many rows the grid has."""
        return self._rows

    @property
    def columns(self):
        """Return how many columns the grid has."""
        return self._columns

    @property
    def room_count(self):
        """Return the total number of rooms in the castle."""
        return len(self._rooms)

    @property
    def walkable_room_count(self):
        """Return how many rooms are not walls.

        The passages form a tree over these rooms only, so this is the
        number the maze invariants are stated in terms of.
        """
        return sum(1 for room in self._rooms.values() if not room.is_wall())

    @property
    def rooms(self):
        """Return a list of every room, in grid order.

        Drawing the map needs to look at all of the rooms at once, so this
        is the convenient way in. The returned list is a copy:
        changing it does not change the castle.
        """
        return [self._rooms[room_id] for room_id in sorted(self._rooms)]

    def room_ids(self):
        """Return every room id, in grid order."""
        return sorted(self._rooms)

    # --- Generation -----------------------------------------------

    @staticmethod
    def generate_random():
        """Return a brand new castle with walls, maze and contents.

        The order of these three calls is the whole trick. The walls go
        up **first**, because a wall has to be standing before the
        depth-first search chooses its passages: that is the only way to
        guarantee the walls end up outside the maze. Dealing the
        contents last then fills only the rooms that are actually
        walkable.
        """
        castle = Castle(Config.MAP_ROWS, Config.MAP_COLUMNS)
        castle._choose_walls()
        castle._build_maze()
        castle._deal_contents()
        return castle

    def _choose_walls(self):
        """Raise ``Config.WALL_ROOMS`` walls without cutting the map.

        Walls go up one at a time and the castle is re-checked after
        each one. Two things can go wrong, and both are checked:

        1. A line of walls can split a 4x4 grid in two, and the
           depth-first search only ever reaches the piece that holds the
           starting room. A treasure stranded in the other piece would
           make the run impossible to win.
        2. A wall can end up ringed by other walls. That does not
           disconnect anything, but it leaves a wall the player could
           never reach, bump into or discover.

        A candidate that breaks either rule is put back and the next one
        is tried. Returns the number of walls actually raised, which is
        ``Config.WALL_ROOMS`` unless the grid was too cramped to allow
        them all.
        """
        candidates = [
            room
            for room in self._rooms.values()
            if room.room_id != Config.STARTING_ROOM
        ]
        random.shuffle(candidates)

        placed = 0
        for room in candidates:
            if placed >= Config.WALL_ROOMS:
                break
            room.place_wall()
            if (self._walkable_area_is_connected()
                    and self._every_wall_can_be_bumped()):
                placed += 1
            else:
                room.place_empty()
        return placed

    def _every_wall_can_be_bumped(self):
        """Return True when no wall is walled in by other walls.

        Every wall must touch at least one walkable room, otherwise the
        player has no way of ever finding it and it is just filler.
        """
        for wall in self._rooms.values():
            if not wall.is_wall():
                continue
            touches_walkable = any(
                self.is_side_by_side(wall.room_id, other_id)
                and not self._rooms[other_id].is_wall()
                for other_id in self._rooms
            )
            if not touches_walkable:
                return False
        return True

    def _walkable_area_is_connected(self):
        """Return True when every walkable room can still be walked to.

        Measured on the grid, ignoring passages, because this runs
        *before* the maze exists. It answers a different question from
        :meth:`visited_count_from`: not "does the maze reach them" but
        "is there any way for the maze to reach them at all".
        """
        walkable = [
            room.room_id
            for room in self._rooms.values()
            if not room.is_wall()
        ]
        if not walkable:
            return False

        start = walkable[0]
        seen = {start}
        stack = [start]
        while stack:
            current_id = stack.pop()
            room = self._rooms[current_id]
            for row, column in (
                (room.row - 1, room.column),
                (room.row + 1, room.column),
                (room.row, room.column - 1),
                (room.row, room.column + 1),
            ):
                if not (0 <= row < self._rows
                        and 0 <= column < self._columns):
                    continue
                other_id = self.id_at(row, column)
                if (other_id not in seen
                        and not self._rooms[other_id].is_wall()):
                    seen.add(other_id)
                    stack.append(other_id)

        return len(seen) == len(walkable)

    def _build_maze(self):
        """Connect every walkable room using a random depth-first search.

        A depth-first search that backtracks can only reach every cell
        of a grid, so this guarantees that **all walkable rooms are
        reachable from the starting room**. Wiring rooms at random
        instead could strand part of the castle, making a run impossible
        to win.

        Walls are skipped rather than connected, which leaves them
        isolated: the passages form a tree over the walkable rooms only.

        A stack replaces the recursion on purpose: it is easier to read
        and to step through in a debugger.
        """
        start = Config.STARTING_ROOM
        visited = {start}
        stack = [start]

        while stack:
            current_id = stack[-1]
            unvisited = self._unvisited_neighbours(current_id, visited)

            if not unvisited:
                # Dead end: step back to the previous room and try
                # again from there.
                stack.pop()
                continue

            next_id = random.choice(unvisited)
            self._rooms[current_id].connect_to(next_id)
            self._rooms[next_id].connect_to(current_id)
            visited.add(next_id)
            stack.append(next_id)

    def _unvisited_neighbours(self, room_id, visited):
        """Return the ids of the reachable rooms not yet visited.

        Only the four orthogonal directions count as passages, so no
        room ever ends up with more than four doors. Walls are filtered
        out as well: the maze must leave them isolated.

        The grid bounds are checked *before* the id is calculated. That
        order matters: ``id_at`` is a plain formula, so asking for
        column 4 of a 4-column grid would return ``4``, which is the
        perfectly valid id of the room at row 1, column 0. Without the
        bounds check the maze would grow passages through the walls.
        """
        room = self._rooms[room_id]
        candidates = (
            (room.row - 1, room.column),  # up
            (room.row + 1, room.column),  # down
            (room.row, room.column - 1),  # left
            (room.row, room.column + 1),  # right
        )

        neighbours = []
        for row, column in candidates:
            if not (0 <= row < self._rows
                    and 0 <= column < self._columns):
                continue
            other_id = self.id_at(row, column)
            if other_id not in visited and not self._rooms[other_id].is_wall():
                neighbours.append(other_id)
        return neighbours

    def _deal_contents(self):
        """Give every walkable room a type, from a fixed shuffled list.

        Using fixed counts instead of per-room dice rolls guarantees a
        winnable castle: there are always exactly ``TREASURE_ROOMS``
        treasures, and ``TREASURE_ROOMS`` piles of 20-40 gold comfortably
        beat ``GOLD_GOAL`` of 60. Walls are skipped here rather than
        dealt with, so they can never soak up a treasure.
        """
        walkable = [
            room for room in self._rooms.values() if not room.is_wall()
        ]
        empty_count = (
            len(walkable) - Config.TREASURE_ROOMS - Config.ENEMY_ROOMS
        )
        types = (
            [RoomType.EMPTY] * empty_count
            + [RoomType.TREASURE] * Config.TREASURE_ROOMS
            + [RoomType.ENEMY] * Config.ENEMY_ROOMS
        )
        random.shuffle(types)

        for room, room_type in zip(walkable, types):
            if room_type is RoomType.TREASURE:
                room.place_treasure()
            elif room_type is RoomType.ENEMY:
                room.place_enemy()
            # EMPTY rooms are already empty, so nothing to do.

        self._empty_the_starting_room()

    def _empty_the_starting_room(self):
        """Make sure the room the player begins in holds nothing.

        The run must never open with an unavoidable fight. Simply
        clearing the starting room would quietly leave the castle short
        of a treasure or an enemy, so instead its contents are traded
        with a random empty room: the fixed counts survive, and the
        player still starts in a safe place.
        """
        start = self._rooms[Config.STARTING_ROOM]
        if start.type is RoomType.EMPTY:
            return

        empty_rooms = [
            room
            for room in self._rooms.values()
            if room.type is RoomType.EMPTY
        ]
        start.swap_contents_with(random.choice(empty_rooms))

    # --- Queries --------------------------------------------------

    def id_at(self, row, column):
        """Return the id of the room at the given grid position."""
        return row * self._columns + column

    def get_room(self, room_id):
        """Return the room with that id, or None if it does not exist."""
        return self._rooms.get(room_id)

    def has_room(self, room_id):
        """Return True when ``room_id`` is a real room of this castle."""
        return room_id in self._rooms

    def neighbours_of(self, room_id):
        """Return the ids of the rooms joined to ``room_id``."""
        room = self.get_room(room_id)
        if room is None:
            return []
        return room.connections

    def is_side_by_side(self, room_id, other_id):
        """Return True when two rooms touch, passaged or not.

        The castle, not the room, can answer this: turning a room id back
        into a ``(row, column)`` pair needs to know how many columns the
        grid has.
        """
        room = self.get_room(room_id)
        other = self.get_room(other_id)
        if room is None or other is None:
            return False
        return room.is_side_by_side(other)

    def walls(self):
        """Return the ids of every wall room, in grid order."""
        return [room.room_id for room in self.rooms if room.is_wall()]

    def visited_count_from(self, start_id):
        """Return how many walkable rooms are reachable from ``start_id``.

        Not needed to play, but it is the easiest way to *prove* that
        the generated maze has no unreachable corner: the test suite
        asserts this equals ``walkable_room_count``.

        Walls are counted out without being asked for, since they are
        left isolated and hold no passages at all.
        """
        if not self.has_room(start_id):
            return 0
        if self._rooms[start_id].is_wall():
            return 1
        seen = {start_id}
        stack = [start_id]
        while stack:
            for other in self.neighbours_of(stack.pop()):
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        return len(seen)
