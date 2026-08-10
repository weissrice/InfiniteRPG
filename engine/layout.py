"""Layout engine for the Infinite RPG UI V2.2.

Calculates exact panel dimensions from terminal size.
Supports both the legacy two-column layout and the new four-quadrant layout.
Every dimension is deterministic and derived from terminal width/height.
Height-aware: body_height accounts for prompt and all fixed UI elements.
"""

from dataclasses import dataclass, field
from typing import List

from .terminal import TerminalSize, visible_width, pad_to_width, wrap_text


# Layout constants
MIN_TWO_COLUMN_WIDTH = 90

# Fixed line counts consumed by the outer UI frame.
# Header: box_top(1) + header_line(1) = 2 lines
HEADER_HEIGHT = 2
# Footer: box_mid(1) + cmd_line(1) + box_bottom(1) = 3 lines
FOOTER_HEIGHT = 3
# Blank line printed by main.py after each render_game()
BLANK_LINE = 1
# Lines reserved for the "> " input prompt
PROMPT_LINES = 1

RIGHT_PANEL_RATIO = 0.35
RIGHT_PANEL_MIN = 24
LEFT_PANEL_MIN = 40


@dataclass
class Layout:
    """Exact dimensions for every screen region."""
    terminal_width: int
    terminal_height: int
    two_column: bool

    header_width: int
    body_width: int
    footer_width: int

    left_width: int
    right_width: int
    gutter_width: int

    body_height: int
    left_height: int
    right_height: int

    right_x: int  # column where right panel starts

    # Four-quadrant layout fields (populated when use_quadrants=True)
    top_height: int = 0
    bottom_height: int = 0
    mid_gutter_height: int = 0

    @classmethod
    def calculate(cls, terminal: TerminalSize = None,
                  use_quadrants: bool = True) -> "Layout":
        if terminal is None:
            terminal = TerminalSize.detect()

        tw = terminal.width
        th = terminal.height

        header_width = tw
        footer_width = tw
        body_width = tw
        gutter_width = 1  # single │ character

        # Body height: total terminal minus header, footer, blank line, prompt
        fixed = HEADER_HEIGHT + FOOTER_HEIGHT + BLANK_LINE + PROMPT_LINES
        body_height = max(1, th - fixed)

        two_column = tw >= MIN_TWO_COLUMN_WIDTH

        if two_column:
            right_w = max(RIGHT_PANEL_MIN, min(int(tw * RIGHT_PANEL_RATIO), tw // 3))
            left_w = tw - right_w - gutter_width
            left_w = max(LEFT_PANEL_MIN, left_w)
            # Recalculate right if left min pushed it
            right_w = tw - left_w - gutter_width
            right_x = left_w + gutter_width
        else:
            left_w = tw
            right_w = 0
            right_x = 0
            gutter_width = 0

        # Four-quadrant split
        if use_quadrants and two_column:
            top_h = body_height // 2
            bot_h = body_height - top_h
        else:
            top_h = body_height
            bot_h = 0

        return cls(
            terminal_width=tw,
            terminal_height=th,
            two_column=two_column,
            header_width=header_width,
            body_width=body_width,
            footer_width=footer_width,
            left_width=left_w,
            right_width=right_w,
            gutter_width=gutter_width,
            body_height=body_height,
            left_height=body_height,
            right_height=body_height,
            right_x=right_x,
            top_height=top_h,
            bottom_height=bot_h,
            mid_gutter_height=0,
        )


def compose_two_columns(left_lines: List[str], right_lines: List[str],
                        left_width: int, right_width: int,
                        gutter_width: int, height: int) -> List[str]:
    """Compose two panels side by side with a gutter separator."""
    gutter = "\u2502" if gutter_width > 0 else ""
    result = []
    for i in range(height):
        l = left_lines[i] if i < len(left_lines) else " " * left_width
        r = right_lines[i] if i < len(right_lines) else " " * right_width
        result.append(l + gutter + r)
    return result


def compose_quad(top_left: List[str], top_right: List[str],
                 bot_left: List[str], bot_right: List[str],
                 layout: "Layout") -> List[str]:
    """Compose four panels into a 2×2 grid with gutters.

    Returns layout.body_height lines, each exactly layout.body_width visible chars.
    """
    lw = layout.left_width
    rw = layout.right_width
    gh = layout.gutter_width
    gutter = "\u2502" if gh > 0 else ""
    th = layout.top_height
    bh = layout.bottom_height

    result = []

    # Top half
    for i in range(th):
        tl = top_left[i] if i < len(top_left) else " " * lw
        tr = top_right[i] if i < len(top_right) else " " * rw
        result.append(tl + gutter + tr)

    # Bottom half
    for i in range(bh):
        bl = bot_left[i] if i < len(bot_left) else " " * lw
        br = bot_right[i] if i < len(bot_right) else " " * rw
        result.append(bl + gutter + br)

    return result


def hline(width: int, char: str = "\u2500") -> str:
    """Generate a horizontal line of exactly width visible characters."""
    return char * width


def box_top(width: int) -> str:
    """Top border: ┌───...───┐"""
    if width < 2:
        return "\u250c" * width
    return "\u250c" + "\u2500" * (width - 2) + "\u2510"


def box_bottom(width: int) -> str:
    """Bottom border: └───...───┘"""
    if width < 2:
        return "\u2514" * width
    return "\u2514" + "\u2500" * (width - 2) + "\u2518"


def box_mid(width: int) -> str:
    """Middle separator: ├───...───┤"""
    if width < 2:
        return "\u251c" * width
    return "\u251c" + "\u2500" * (width - 2) + "\u2524"


def box_line(text: str, width: int) -> str:
    """Boxed content line: │ <text> │ with padding to width."""
    if width < 2:
        return text[:width]
    inner_width = width - 2
    padded = pad_to_width(text, inner_width)
    return "\u2502" + padded + "\u2502"


def wrap_in_panel(text: str, panel_width: int, indent: int = 2) -> list:
    """Wrap text to fit within a panel, with indentation on each line."""
    effective_width = max(1, panel_width - indent)
    lines = wrap_text(text, effective_width)
    prefix = " " * indent
    return [prefix + line for line in lines]


def render_bar(current: int, maximum: int, width: int = 20) -> str:
    """Render a progress bar: ████████░░░░ 72/100"""
    if maximum <= 0:
        pct = 0.0
    else:
        pct = max(0.0, min(1.0, current / maximum))

    bar_width = max(0, width - 5)
    filled = int(pct * bar_width)
    empty = bar_width - filled

    bar = "\u2588" * filled + "\u2591" * empty
    return f"{bar} {current}/{maximum}"


def render_kv(key: str, value: str, key_width: int = 6) -> str:
    """Render a key-value pair: '  KEY   value'"""
    return f"  {key:<{key_width}}{value}"
