"""The guard that blocks a room until the player solves a problem."""

import random

from config import Config
from models.operation import MathOperation


class Enemy:
    """A castle guard that asks one maths problem at a time.

    The enemy owns the question it is currently asking. When the player
    answers wrongly the enemy asks a *new* question, which is why
    ``pose_question()`` is called again instead of reusing the old
    problem.
    """

    def __init__(self, name, damage):
        """Store the enemy name, the damage it deals and its state."""
        self._name = name
        self._damage = damage
        self._is_defeated = False
        self._question = None

    @staticmethod
    def create_random():
        """Return a new enemy with a random name."""
        name = random.choice(Config.ENEMY_NAMES)
        return Enemy(name, Config.ENEMY_DAMAGE)

    @property
    def name(self):
        """Return the enemy's name, used in the interface and log."""
        return self._name

    @property
    def damage(self):
        """Return how much health a wrong answer costs the player."""
        return self._damage

    @property
    def question(self):
        """Return the problem the enemy is asking right now."""
        return self._question

    def pose_question(self):
        """Ask a brand new problem and return it.

        Called when the enemy appears and again after every wrong
        answer, so the player never sees the same problem twice in a
        row.
        """
        self._question = MathOperation.create_random()
        return self._question

    def defeat(self):
        """Mark the enemy as beaten."""
        self._is_defeated = True

    def is_defeated(self):
        """Return True once the enemy has been beaten."""
        return self._is_defeated
