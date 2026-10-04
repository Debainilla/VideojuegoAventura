"""The maths problem an enemy asks the player to solve."""

import random

from config import Config


class MathOperation:
    """A single arithmetic problem, for example ``7 + 8 = ?``.

    This class knows how to build itself at random and how to judge an
    answer. It deliberately knows nothing about players or enemies:
    whoever asks the question and whoever answers it lives elsewhere.
    """

    def __init__(self, first, second, operator, result):
        """Store the two operands, the operator and the result."""
        self._first = first
        self._second = second
        self._operator = operator
        self._result = result

    @staticmethod
    def create_random():
        """Return a new operation with random numbers and operator."""
        operator = random.choice(Config.OPERATORS)
        first = random.randint(Config.OPERAND_MIN, Config.OPERAND_MAX)
        second = random.randint(Config.OPERAND_MIN, Config.OPERAND_MAX)

        if operator == "-" and first < second:
            # Swap the operands so the answer is never a negative
            # number. Negative results confuse players of any age and
            # would force us to handle them everywhere else.
            first, second = second, first

        if operator == "+":
            result = first + second
        elif operator == "-":
            result = first - second
        else:  # "x" (multiplication)
            result = first * second

        return MathOperation(first, second, operator, result)

    @property
    def text(self):
        """Return the problem exactly as the player will read it."""
        return f"{self._first} {self._operator} {self._second} = ?"

    def is_correct(self, answer):
        """Return True when ``answer`` solves the problem.

        Anything that is not a plain integer -- an empty string,
        a word, ``"3.5"`` -- counts as a wrong answer. The engine
        turns a wrong answer into damage, so being strict here is the
        safe choice.
        """
        try:
            return int(str(answer).strip()) == self._result
        except (TypeError, ValueError):
            return False
