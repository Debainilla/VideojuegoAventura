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
    def rooms(self):
        """Return a list of every room, in grid order.

        Drawing the map needs to look at all of the rooms at once, so
        this is the convenient way in. The returned list is a copy:
        changing it does not change the castle.
        """
        return [self._rooms[room_id] for room_id in sorted(self._rooms)]

    def room_ids(self):
        """Return every room id, in grid order."""
        return sorted(self._rooms)

    # --- Generation -----------------------------------------------

    @staticmethod
    def generate_random():
        """Return a brand new castle with a random maze and contents.

        The constructor already made every room, so this only has two
        jobs left: wire the rooms into a maze, then deal the contents.
        """
        castle = Castle(Config.MAP_ROWS, Config.MAP_COLUMNS)
        castle._build_maze()
        castle._deal_contents()
        return castle

    def _build_maze(self):
        """Connect every room using a random depth-first search.

        A depth-first search that backtracks can only reach every cell
        of a grid, so this guarantees that **all rooms are reachable
        from the starting room**. Wiring rooms at random instead could
        strand part of the castle, making a run impossible to win.

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
        room ever ends up with more than four doors.

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
            if other_id not in visited:
                neighbours.append(other_id)
        return neighbours

    def _deal_contents(self):
        """Give every room a type, dealing from a fixed shuffled list.

        Using fixed counts instead of per-room dice rolls guarantees a
        winnable castle: there are always exactly ``TREASURE_ROOMS``
        treasures, and ``TREASURE_ROOMS`` piles of 20-40 gold
        comfortably beat ``GOLD_GOAL`` of 60.
        """
        total = self.room_count
        empty_count = total - Config.TREASURE_ROOMS - Config.ENEMY_ROOMS
        types = (
            [RoomType.EMPTY] * empty_count
            + [RoomType.TREASURE] * Config.TREASURE_ROOMS
            + [RoomType.ENEMY] * Config.ENEMY_ROOMS
        )
        random.shuffle(types)

        for room, room_type in zip(self._rooms.values(), types):
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

    def visited_count_from(self, start_id):
        """Return how many rooms are reachable from ``start_id``.

        Not needed to play, but it is the easiest way to *prove* that
        the generated maze has no unreachable corner: the test suite
        asserts this equals ``room_count``.
        """
        if not self.has_room(start_id):
            return 0
        seen = {start_id}
        stack = [start_id]
        while stack:
            for other in self.neighbours_of(stack.pop()):
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        return len(seen)
