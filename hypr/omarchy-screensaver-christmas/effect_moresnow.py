"""Snow falls and accumulates, gradually revealing the text as snowflakes stick to it.

Classes:
    MoreSnow: Snow falls continuously with some sticking to reveal the text.
    MoreSnowConfig: Configuration for the MoreSnow effect.
    MoreSnowIterator: Iterator for the MoreSnow effect. Does not normally need to be called directly.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from terminaltexteffects import Color, Coord, EffectCharacter, Gradient, easing
from terminaltexteffects.engine.base_config import BaseConfig
from terminaltexteffects.engine.base_effect import BaseEffect, BaseEffectIterator
from terminaltexteffects.utils import argutils
from terminaltexteffects.utils.argutils import ArgSpec, ParserSpec
from terminaltexteffects.utils.graphics import ColorPair


def get_effect_resources() -> tuple[str, type[BaseEffect], type[BaseConfig]]:
    """Get the command, effect class, and configuration class for the effect.

    Returns:
        tuple[str, type[BaseEffect], type[BaseConfig]]: The command name, effect class, and configuration class.

    """
    return "moresnow", MoreSnow, MoreSnowConfig


@dataclass
class MoreSnowConfig(BaseConfig):
    """Configuration for the MoreSnow effect.

    Attributes:
        snow_colors (tuple[Color, ...]): Colors for the falling snow.
        snow_symbols (tuple[str, ...]): Symbols to use for snowflakes.
        final_gradient_stops (tuple[Color, ...]): Colors for the final gradient.
        final_gradient_steps (tuple[int, ...] | int): Number of gradient steps.
        final_gradient_direction (Gradient.Direction): Direction of the final gradient.
        movement_speed (float): Speed of falling snow.

    """

    parser_spec: ParserSpec = ParserSpec(
        name="moresnow",
        help="Snow falls and accumulates, gradually revealing the text.",
        description="moresnow | Snow falls and gradually reveals the text as it sticks.",
        epilog=(
            "Example: terminaltexteffects moresnow --snow-colors ffffff e0ffff b0e0e6 "
            "--final-gradient-stops ff0000 00ff00 ffd700"
        ),
    )

    snow_colors: tuple[Color, ...] = ArgSpec(
        name="--snow-colors",
        type=argutils.ColorArg.type_parser,
        metavar=argutils.ColorArg.METAVAR,
        nargs="+",
        action=argutils.TupleAction,
        default=(Color("ffffff"), Color("e0ffff"), Color("b0e0e6")),
        help="Space separated list of colors for the falling snow.",
    )  # pyright: ignore[reportAssignmentType]
    "tuple[Color, ...] : Colors for the falling snow."

    snow_symbols: tuple[str, ...] = ArgSpec(
        name="--snow-symbols",
        type=argutils.Symbol.type_parser,
        nargs="+",
        action=argutils.TupleAction,
        default=("*", ".", "o", "+"),
        metavar=argutils.Symbol.METAVAR,
        help="Space separated list of symbols to use for snowflakes.",
    )  # pyright: ignore[reportAssignmentType]
    "tuple[str, ...] : Symbols to use for snowflakes."

    movement_speed: float = ArgSpec(
        name="--movement-speed",
        type=argutils.PositiveFloat.type_parser,
        default=0.1,
        metavar=argutils.PositiveFloat.METAVAR,
        help="Movement speed of the snowflakes.",
    )  # pyright: ignore[reportAssignmentType]
    "float : Movement speed of the snowflakes."

    final_gradient_stops: tuple[Color, ...] = ArgSpec(
        name="--final-gradient-stops",
        type=argutils.ColorArg.type_parser,
        nargs="+",
        action=argutils.TupleAction,
        default=(Color("ff0000"), Color("00ff00"), Color("ffd700")),
        metavar=argutils.ColorArg.METAVAR,
        help="Space separated, unquoted, list of colors for the character gradient.",
    )  # pyright: ignore[reportAssignmentType]
    "tuple[Color, ...] : Colors for the final gradient."

    final_gradient_steps: tuple[int, ...] | int = ArgSpec(
        name="--final-gradient-steps",
        type=argutils.PositiveInt.type_parser,
        nargs="+",
        action=argutils.TupleAction,
        default=12,
        metavar=argutils.PositiveInt.METAVAR,
        help="Number of gradient steps to use.",
    )  # pyright: ignore[reportAssignmentType]
    "tuple[int, ...] | int : Number of gradient steps."

    final_gradient_direction: Gradient.Direction = ArgSpec(
        name="--final-gradient-direction",
        type=argutils.GradientDirection.type_parser,
        default=Gradient.Direction.HORIZONTAL,
        metavar=argutils.GradientDirection.METAVAR,
        help="Direction of the final gradient.",
    )  # pyright: ignore[reportAssignmentType]
    "Gradient.Direction : Direction of the final gradient."


class MoreSnowIterator(BaseEffectIterator[MoreSnowConfig]):
    """Iterator for the MoreSnow effect."""

    def __init__(self, effect: MoreSnow) -> None:
        """Initialize the effect iterator.

        Args:
            effect (MoreSnow): The effect to use for the iterator.

        """
        super().__init__(effect)
        self.pending_chars: list[EffectCharacter] = []
        self.background_snow: list[EffectCharacter] = []
        self.bottom_pile_height: dict[int, int] = {}
        self.text_spawn_delay: int = 0
        self.background_spawn_delay: int = 0
        self.text_complete: bool = False
        self.fadeout_counter: int = 0
        self.spawn_stopped: bool = False
        self.build()

    def is_outline_character(self, character: EffectCharacter) -> bool:
        """Check if a character is on the outline (has at least one space neighbor).

        Args:
            character: The character to check.

        Returns:
            bool: True if character is on the outline, False if interior.
        """
        coord = character.input_coord
        # Check all 4 neighbors (up, down, left, right)
        neighbors = [
            Coord(coord.column, coord.row - 1),  # up
            Coord(coord.column, coord.row + 1),  # down
            Coord(coord.column - 1, coord.row),  # left
            Coord(coord.column + 1, coord.row),  # right
        ]

        # If any neighbor is a space (or doesn't exist), this is an outline character
        all_chars = {char.input_coord: char for char in self.terminal.get_characters()}
        for neighbor_coord in neighbors:
            if neighbor_coord not in all_chars:
                return True  # Edge of text = outline
        return False

    def build(self) -> None:
        """Build the initial state of the effect."""
        # Get all characters sorted by position (top to bottom, left to right)
        all_chars = sorted(self.terminal.get_characters(), key=lambda c: (c.input_coord.row, c.input_coord.column))

        # Create index mapping for alternating colors
        char_to_index = {char: idx for idx, char in enumerate(all_chars)}

        # Setup text characters - falling snow effect
        for character in self.terminal.get_characters():
            character.layer = 2  # In front of background snow

            # Snow appearance while falling - exclude "." for text characters
            text_snow_symbols = [s for s in self.config.snow_symbols if s != "."]
            snow_symbol = random.choice(text_snow_symbols) if text_snow_symbols else random.choice(self.config.snow_symbols)
            snow_color = random.choice(self.config.snow_colors)
            falling_scene = character.animation.new_scene()
            falling_scene.add_frame(snow_symbol, 1, colors=ColorPair(fg=snow_color))

            # Landed appearance - horizontal lines of white, green, red
            landed_scene = character.animation.new_scene()
            # Alternate colors by row: white, green, red, white, green, red...
            row_mod = character.input_coord.row % 3
            if row_mod == 0:
                landed_color = Color("ffffff")  # White
            elif row_mod == 1:
                landed_color = Color("33cc33")  # Christmas green
            else:  # row_mod == 2
                landed_color = Color("ff6666")  # Christmas red
            landed_scene.add_frame(character.input_symbol, 1, colors=ColorPair(fg=landed_color))

            character.animation.activate_scene(falling_scene)

            # Start above the canvas and fall to input position
            character.motion.set_coordinate(Coord(character.input_coord.column, self.terminal.canvas.top))

            # Create falling path with swaying
            snowflake_speed = self.config.movement_speed * random.uniform(0.7, 1.3)
            fall_path = character.motion.new_path(speed=snowflake_speed, ease=easing.in_out_sine)

            # Add some sway waypoints
            num_sways = random.randint(2, 4)
            fall_distance = self.terminal.canvas.top - character.input_coord.row
            current_column = character.input_coord.column

            for i in range(1, num_sways):
                progress = i / num_sways
                sway_row = self.terminal.canvas.top - int(fall_distance * progress)
                sway_direction = 1 if i % 2 == 0 else -1
                sway_amount = random.randint(1, 3)
                current_column = current_column + (sway_direction * sway_amount)
                sway_column = max(self.terminal.canvas.left, min(self.terminal.canvas.right, current_column))
                fall_path.new_waypoint(Coord(sway_column, sway_row))

            # Final waypoint at input position
            fall_path.new_waypoint(character.input_coord)

            # Switch to landed color when path completes
            character.event_handler.register_event(
                character.event_handler.Event.PATH_COMPLETE,
                fall_path,
                character.event_handler.Action.ACTIVATE_SCENE,
                landed_scene,
            )

            character.motion.activate_path(fall_path)
            self.pending_chars.append(character)

        # Sort by row (bottom to top) so bottom letters fill first
        self.pending_chars.sort(key=lambda c: c.input_coord.row, reverse=True)

    def spawn_background_snowflake(self, speed_multiplier: float = 1.0) -> None:
        """Spawn a background snowflake that falls to the bottom.

        Args:
            speed_multiplier: Multiplier for the falling speed (default 1.0).
        """
        snow_col = random.randint(self.terminal.canvas.left, self.terminal.canvas.right)
        snow_char = self.terminal.add_character(" ", Coord(snow_col, self.terminal.canvas.top))
        snow_char.layer = 1  # Behind text characters

        # Snow appearance
        snow_symbol = random.choice(self.config.snow_symbols)
        snow_color = random.choice(self.config.snow_colors)
        snow_scene = snow_char.animation.new_scene()
        snow_scene.add_frame(snow_symbol, 1, colors=ColorPair(fg=snow_color))
        snow_char.animation.activate_scene(snow_scene)

        # Set starting position at top
        snow_char.motion.set_coordinate(Coord(snow_col, self.terminal.canvas.top))

        # Create falling path with swaying - using same logic as text snow
        snowflake_speed = self.config.movement_speed * random.uniform(0.7, 1.3) * speed_multiplier
        fall_path = snow_char.motion.new_path(speed=snowflake_speed, ease=easing.in_out_sine)

        # Add sway waypoints - use subtraction like text snow does
        num_sways = random.randint(2, 4)
        fall_distance = self.terminal.canvas.top - self.terminal.canvas.bottom
        current_column = snow_col

        for i in range(1, num_sways):
            progress = i / num_sways
            sway_row = self.terminal.canvas.top - int(fall_distance * progress)
            sway_direction = 1 if i % 2 == 0 else -1
            sway_amount = random.randint(1, 3)
            current_column = current_column + (sway_direction * sway_amount)
            sway_column = max(self.terminal.canvas.left, min(self.terminal.canvas.right, current_column))
            fall_path.new_waypoint(Coord(sway_column, sway_row))

        # Final waypoint at bottom
        final_column = max(self.terminal.canvas.left, min(self.terminal.canvas.right, current_column))
        fall_path.new_waypoint(Coord(final_column, self.terminal.canvas.bottom))

        snow_char.motion.activate_path(fall_path)
        self.terminal.set_character_visibility(snow_char, is_visible=True)
        self.active_characters.add(snow_char)
        self.background_snow.append(snow_char)

    def check_background_snow_landing(self) -> None:
        """Check if background snow has landed and stack it."""
        for snow in list(self.background_snow):
            if not snow.motion.active_path:
                snow_coord = snow.motion.current_coord
                landing_column = snow_coord.column

                if landing_column not in self.bottom_pile_height:
                    self.bottom_pile_height[landing_column] = 0

                # Stack snow at bottom (max height 5) - subtract to stack upward
                if self.bottom_pile_height[landing_column] < 5:
                    stacked_row = self.terminal.canvas.bottom - self.bottom_pile_height[landing_column]
                    snow.motion.set_coordinate(Coord(landing_column, stacked_row))
                    self.bottom_pile_height[landing_column] += 1
                else:
                    # Pile is full, remove this snowflake
                    self.terminal.set_character_visibility(snow, is_visible=False)
                    self.background_snow.remove(snow)

    def __next__(self) -> str:
        """Return the next frame in the animation."""
        # Spawn text-forming snow
        if self.pending_chars:
            if self.text_spawn_delay <= 0:
                # Release only 1 character at a time, less frequently
                if self.pending_chars:
                    next_character = self.pending_chars.pop(random.randint(0, len(self.pending_chars) - 1))
                    self.terminal.set_character_visibility(next_character, is_visible=True)
                    self.active_characters.add(next_character)
                self.text_spawn_delay = 1  # Delay between text snow
            else:
                self.text_spawn_delay -= 1
        elif not self.text_complete:
            # Check if all text characters have landed (completed their paths and turned red)
            all_text_landed = not self.pending_chars
            if all_text_landed:
                # Check if any text characters still have active paths
                for char in self.terminal.get_characters():
                    if char.motion.active_path:
                        all_text_landed = False
                        break

            if all_text_landed:
                # Text completely filled with red, start fadeout
                self.text_complete = True
                # Speed up all existing background snow by creating new fast paths
                for snow in self.background_snow:
                    if snow.motion.active_path:
                        # Get current position
                        current_pos = snow.motion.current_coord
                        # Create new fast path from current position to bottom
                        fast_speed = self.config.movement_speed * 5.0  # Half as fast (5x instead of 10x)
                        new_path = snow.motion.new_path(speed=fast_speed, ease=easing.in_quad)
                        new_path.new_waypoint(Coord(current_pos.column, self.terminal.canvas.bottom))
                        snow.motion.activate_path(new_path)

        # Spawn background snowflakes with fadeout
        if not self.spawn_stopped:
            if self.text_complete:
                self.fadeout_counter += 1
                if self.fadeout_counter > 100:  # Stop spawning after ~0.8 seconds at 120fps
                    self.spawn_stopped = True
                else:
                    if self.background_spawn_delay <= 0:
                        # During fadeout: spawn many fast snowflakes
                        for _ in range(random.randint(5, 10)):
                            # Speed increase - 5x faster
                            self.spawn_background_snowflake(speed_multiplier=5.0)
                        self.background_spawn_delay = 1
                    else:
                        self.background_spawn_delay -= 1
            else:
                # Normal spawning before fadeout
                if self.background_spawn_delay <= 0:
                    for _ in range(random.randint(3, 6)):
                        self.spawn_background_snowflake()
                    self.background_spawn_delay = 2
                else:
                    self.background_spawn_delay -= 1

        # Check background snow landing
        self.check_background_snow_landing()

        # End when spawning stopped and all background snow is gone
        if self.spawn_stopped and len(self.background_snow) == 0:
            raise StopIteration

        # Keep animation running
        self.update()
        return self.frame


class MoreSnow(BaseEffect[MoreSnowConfig]):
    """Snow falls and accumulates, gradually revealing the text.

    Attributes:
        effect_config (MoreSnowConfig): Configuration for the effect.
        terminal_config (TerminalConfig): Configuration for the terminal.

    """

    _config_cls = MoreSnowConfig
    _iterator_cls = MoreSnowIterator
