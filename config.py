"""Every value that shapes how the game feels.

Keeping the numbers in a single file means the game can be rebalanced
without touching the logic, and a reader can understand the whole
design from one short file. No other module should contain a
hard-coded game value.
"""


class Config:
    """Read-only collection of game settings.

    This class is never instantiated: it is used as a namespace, for
    example ``Config.STARTING_HEALTH``. That is exactly why every
    value is written in UPPER_SNAKE_CASE, the PEP 8 convention for
    constants.

    The ``N``, ``Z`` and "gold goal" mentioned in the project brief map
    to the values below.
    """

    # --- Player ---------------------------------------------------
    STARTING_HEALTH = 20          # N: health points the player begins with
    PLAYER_NAME = "Adventurer"

    # --- Enemies --------------------------------------------------
    ENEMY_DAMAGE = 5              # Z: damage of every wrong answer
    # Set GOLD_PER_ENEMY to 0 to make gold come only from treasure rooms.
    GOLD_PER_ENEMY = 10           # Z: gold for beating an enemy
    ENEMY_NAMES = (
        "Iron Guardian",
        "Soul Goblin",
        "Skeleton Guard",
        "Hallway Wizard",
        "Giant Rat",
    )

    # --- Gold -----------------------------------------------------
    GOLD_GOAL = 60                # gold needed to win the game
    TREASURE_GOLD_MIN = 20
    TREASURE_GOLD_MAX = 40

    # --- Map ------------------------------------------------------
    MAP_ROWS = 4
    MAP_COLUMNS = 4
    TREASURE_ROOMS = 4
    ENEMY_ROOMS = 3
    # How many rooms are solid walls. Walls are left out of the maze
    # altogether, so they can never block the way to a treasure and the
    # run stays winnable whatever this number is.
    WALL_ROOMS = 3
    STARTING_ROOM = 0

    # --- Maths problem --------------------------------------------
    ANSWER_TIME_LIMIT = 20        # seconds allowed to answer
    OPERATORS = ("+", "-", "x")   # "x" reads better than a times sign
    OPERAND_MIN = 2
    OPERAND_MAX = 9

    # --- Interface ------------------------------------------------
    TIMER_REFRESH_SECONDS = 0.5   # how often the countdown redraws
    VISIBLE_LOG_LINES = 8
    MAX_LOG_ENTRIES = 50          # keeps the log from growing forever

    # Map symbols. Streamlit ships the Material Symbols font, so any
    # ":material/snake_case_name:" string renders as an icon. Swap
    # these for anything you like.
    ICON_EMPTY = ":material/door_front:"
    ICON_TREASURE = ":material/diamond:"
    ICON_ENEMY = ":material/sports_martial_arts:"
    ICON_PLAYER = ":material/person_pin_circle:"
    ICON_WALL = ":material/wallpaper:"
    # Shown on a room the player has not explored yet: the cell is
    # visible, but what is inside it is not.
    ICON_UNKNOWN = ":material/question_mark:"
