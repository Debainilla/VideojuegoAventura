"""The Streamlit interface of the castle adventure.

This file is the *only* place that knows about Streamlit. The rules all
live in :mod:`game` and :mod:`models`, which know nothing about the
interface, so they can be tested from a terminal with::

    python -m tests.test_game

Two ideas do most of the work here:

1. The run is kept in ``st.session_state`` under the key ``"game"``.
   Streamlit reruns this whole file on every click, so without that the
   castle would be rebuilt each time and the player would forget
   everything.

2. Widgets change state through **callbacks** rather than by reading
   the widget afterwards. A callback runs before the script body, which
   keeps the "what just happened" logic in one place and stops a
   half-drawn page from ever changing the game.
"""

import streamlit as st

from config import Config
from game import Game, GameState

# Keys used inside st.session_state. Naming them here means the same
# string is never typed twice by hand.
GAME_KEY = "game"
ANSWER_KEY = "answer"
MESSAGE_KEY = "message"


# --- State and callbacks ------------------------------------------

def get_game():
    """Return the current run, creating it on the very first visit.

    ``st.session_state`` behaves like a dictionary that survives
    reruns. Building the game only when the key is missing means a new
    castle is generated once, not once per click.
    """
    if GAME_KEY not in st.session_state:
        st.session_state[GAME_KEY] = Game.new_game()
        st.session_state[ANSWER_KEY] = ""
        st.session_state[MESSAGE_KEY] = "A new castle awaits. Good luck!"
    return st.session_state[GAME_KEY]


def start_new_game():
    """Callback for the "New game" button: throw the run away."""
    st.session_state[GAME_KEY] = Game.new_game()
    st.session_state[ANSWER_KEY] = ""
    st.session_state[MESSAGE_KEY] = "A new castle awaits. Good luck!"


def move_to_room(room_id):
    """Callback for a map button: try to walk into that room."""
    game = get_game()
    st.session_state[MESSAGE_KEY] = game.move_to(room_id)
    st.session_state[ANSWER_KEY] = ""


def submit_answer():
    """Callback for the "Solve" button: judge the typed answer."""
    game = get_game()
    st.session_state[MESSAGE_KEY] = game.submit_answer(
        st.session_state.get(ANSWER_KEY, "")
    )
    # Clearing the box is friendlier than leaving a stale number in it.
    st.session_state[ANSWER_KEY] = ""


# --- The map -------------------------------------------------------

def draw_map(game):
    """Draw the whole castle as a grid of buttons.

    The grid is always fully drawn, so the shape of the castle stays
    readable, but **the contents of a room stay hidden until it is
    found**: an unexplored room shows a question mark. Two kinds of
    button are live:

    * every room joined to the one the player stands in, because there
      is a passage to walk through;
    * every *unexplored* room that merely touches it, because the player
      has to be allowed to try. That attempt is what discovers a wall.

    Once a wall has been found its button is disabled, so the map
    settles down into what is actually known.
    """
    st.subheader("Castle map")
    castle = game.castle
    position = game.player.position
    reachable = set(castle.neighbours_of(position))
    can_walk = game.can_move()

    for row in range(Config.MAP_ROWS):
        columns = st.columns(Config.MAP_COLUMNS)
        for column in range(Config.MAP_COLUMNS):
            room_id = castle.id_at(row, column)
            room = castle.get_room(room_id)
            with columns[column]:
                draw_room_button(
                    game, room, room_id, reachable, can_walk
                )


def draw_room_button(game, room, room_id, reachable, can_walk):
    """Draw the single button for one room of the map.

    Six cases, in the order the player cares about:

    * the room they are standing in (pressed, cannot be clicked);
    * a room with a passage to it (clickable, walk in);
    * an unexplored room touching them (clickable, try to go that way,
      which is how a wall gets discovered);
    * a wall they have already found (shown, locked);
    * a room they know about but cannot reach from here (locked);
    * anything else would be a bug, so it is reported rather than
      hidden.

    The icon comes from ``room.icon``, which already applies the fog of
    war, so this function never has to think about what a room holds.
    """
    castle = game.castle
    here = game.player.position

    if room_id == here:
        button_type, label, icon = "primary", "You", Config.ICON_PLAYER
        clicked, help_text = True, "This is where you are."
    elif room_id in reachable and can_walk:
        button_type, label, icon = "secondary", str(room_id), room.icon
        clicked, help_text = False, "Walk through here."
    elif can_walk and castle.is_side_by_side(here, room_id) \
            and not room.discovered:
        # Undiscovered and touching: the player may try to go there.
        # Either a passage was hiding and they walk in, or it is a wall
        # and they learn that instead.
        button_type, label, icon = "secondary", str(room_id), room.icon
        clicked, help_text = False, "Try to go that way."
    elif room.is_wall() and room.discovered:
        button_type, label, icon = "secondary", str(room_id), room.icon
        clicked = True
        help_text = "A solid wall. You already found it."
    elif castle.has_room(room_id):
        button_type, label, icon = "secondary", str(room_id), room.icon
        clicked = True
        help_text = "There is no passage from where you stand."
    else:
        button_type, label, icon = "secondary", "?", Config.ICON_UNKNOWN
        clicked, help_text = True, "This room does not exist."

    st.button(
        label,
        key=f"room_{room_id}",
        help=help_text,
        type=button_type,
        icon=icon,
        disabled=clicked,
        width="stretch",
        on_click=move_to_room,
        args=(room_id,),
    )


# --- The countdown -------------------------------------------------

@st.fragment(run_every=Config.TIMER_REFRESH_SECONDS)
def draw_countdown():
    """Redraw the countdown twice a second while a fight is on.

    ``@st.fragment`` reruns only this little piece, so the page is not
    rebuilt twenty times a minute. The text box for the answer is
    deliberately **outside** this fragment: re-rendering an input
    while the player is typing would fight the keyboard.

    ``Game.time_remaining()`` subtracts from an absolute deadline
    instead of counting down, so a slow or skipped refresh can never
    make the clock drift. When the deadline does pass, the penalty is
    applied here and ``st.rerun()`` redraws the whole page.
    """
    game = get_game()
    if not game.in_combat:
        return

    remaining = game.time_remaining()
    if remaining <= 0:
        st.session_state[MESSAGE_KEY] = game.register_timeout()
        st.rerun()  # the map and health changed: redraw everything
        return

    st.progress(
        remaining / Config.ANSWER_TIME_LIMIT,
        text=f"Time left: {remaining:0.0f} of "
             f"{Config.ANSWER_TIME_LIMIT} seconds",
    )


# --- Panels -------------------------------------------------------

def draw_status(game):
    """Draw the row of numbers that describes the run."""
    gold_left = max(0, Config.GOLD_GOAL - game.player.gold)
    columns = st.columns(5)
    columns[0].metric(
        "Health", f"{game.player.health}",
        delta=f"-{Config.ENEMY_DAMAGE} per mistake",
        delta_color="off",
        icon=":material/favorite:",
        border=True,
    )
    columns[1].metric(
        "Gold", f"{game.player.gold}",
        delta=f"{gold_left} to the goal",
        delta_color="off",
        icon=":material/diamond:",
        border=True,
    )
    columns[2].metric(
        "Room", str(game.player.position),
        help="The room you are standing in.",
        icon=Config.ICON_PLAYER,
        border=True,
    )
    columns[3].metric(
        "Enemies beaten", str(game.enemies_defeated),
        help="How many enemies you have defeated.",
        icon=Config.ICON_ENEMY,
        border=True,
    )
    columns[4].metric(
        "Explored",
        f"{game.discovered_count}/{game.castle.room_count}",
        delta=f"{game.walls_found} wall(s) found",
        delta_color="off",
        help=(
            "How much of the castle you have uncovered. Walls count as "
            "explored once you have bumped into them."
        ),
        icon=Config.ICON_UNKNOWN,
        border=True,
    )


def draw_combat(game):
    """Draw the maths problem, or say why there is nothing to solve."""
    if not game.in_combat:
        st.info("Walk to a room marked with a warrior to start a fight.")
        return

    enemy = game.current_room().enemy
    st.error(f"{enemy.name} is blocking the way. Solve to get past!")
    st.markdown(f"### {enemy.question.text}")
    draw_countdown()

    left, right = st.columns([3, 1])
    with left:
        st.text_input(
            "Your answer",
            key=ANSWER_KEY,
            placeholder="Type the number",
            label_visibility="collapsed",
        )
    with right:
        st.button(
            "Solve",
            key="solve",
            type="primary",
            width="stretch",
            on_click=submit_answer,
        )


def draw_end_of_run(game):
    """Draw the closing screen once the run is decided."""
    if game.state is GameState.VICTORY:
        st.success("You won! The castle is yours.")
    elif game.state is GameState.DEFEAT:
        st.error("You fell in the castle. Better luck next time.")
    else:
        return

    st.markdown(
        f"- Rooms entered: **{game.rooms_visited}**\n"
        f"- Rooms explored: **{game.discovered_count}** of "
        f"{game.castle.room_count}\n"
        f"- Walls found: **{game.walls_found}**\n"
        f"- Enemies beaten: **{game.enemies_defeated}**\n"
        f"- Gold gathered: **{game.player.gold}**"
    )


def draw_log(game):
    """Draw the adventure log, newest line first."""
    with st.expander("Adventure log"):
        lines = game.log[-Config.VISIBLE_LOG_LINES:]
        for line in reversed(lines):
            st.markdown(line)


# --- The page -----------------------------------------------------

def main():
    """Draw the whole page, in the order a player reads it."""
    game = get_game()

    st.title("Castle Adventure")
    st.caption(
        f"Collect {Config.GOLD_GOAL} gold to win. You start with "
        f"{Config.STARTING_HEALTH} health, and every wrong answer in a "
        f"fight costs {Config.ENEMY_DAMAGE}. Rooms you have not found "
        f"yet show a question mark, and some rooms are solid walls."
    )

    st.button(
        "New game",
        key="new_game",
        icon=":material/casino:",
        on_click=start_new_game,
    )

    draw_status(game)
    st.divider()
    draw_map(game)
    st.divider()
    draw_combat(game)

    if st.session_state[MESSAGE_KEY]:
        st.info(st.session_state[MESSAGE_KEY])

    draw_end_of_run(game)
    draw_log(game)


if __name__ == "__main__":
    main()
