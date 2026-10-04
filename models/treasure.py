"""The gold hidden in a treasure room."""

import random

from config import Config


class Treasure:
    """A pile of gold waiting to be picked up.

    A room that contains a treasure also *contains* this object, and
    the room gives it up (and then becomes empty) exactly once, so the
    same gold can never be collected twice.
    """

    def __init__(self, gold):
        """Store how much gold this treasure is worth."""
        self._gold = gold

    @staticmethod
    def create_random():
        """Return a new treasure worth a random amount of gold."""
        gold = random.randint(
            Config.TREASURE_GOLD_MIN,
            Config.TREASURE_GOLD_MAX,
        )
        return Treasure(gold)

    def amount(self):
        """Return the number of gold coins in this treasure."""
        return self._gold
