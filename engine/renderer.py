"""Rich-native renderer for Infinite RPG UI V3.0 Phase B.

Rich Layout owns the screen geometry.  Panel renderers produce Rich
renderables.  Rich Console renders the final output.

Layout hierarchy::

    ROOT (split_column)
    ├── HEADER  (Panel, size=3)
    ├── BODY
    │   ├── Two-column (width >= 90):
    │   │   └── split_row
    │   │       ├── LEFT
    │   │       │   ├── WORLD_MAP  (top half)
    │   │       │   └── INFO       (bottom half: location, narration, player, quests)
    │   │       └── RIGHT
    │   │           ├── MINIMAP    (top half)
    │   │           └── SIDE       (bottom half: inventory, skills)
    │   └── Single-column (width < 90):
    │       ├── TEXT_CONTENT  (location, narration, player, quests)
    │       └── MAP           (world map)
    └── FOOTER  (Panel, size=3)
"""

import os
from io import StringIO

from rich import box
from rich.box import Box as _Box
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .state import GameState
from .terminal import TerminalSize, colors_enabled
from .layout import MIN_TWO_COLUMN_WIDTH, render_bar, render_kv
from .world_map import render_world_map, render_minimap


# Box style with no visible borders (used for height-clamping panels)
_NO_BORDER = _Box.__new__(_Box)
for _attr in ['top', 'top_double', 'top_left', 'top_right',
              'bottom', 'bottom_double', 'bottom_left', 'bottom_right',
              'left', 'right', 'header',
              'row_horizontal', 'row_left', 'row_right', 'row_cross',
              'head_row_horizontal', 'head_row_left', 'head_row_right', 'head_row_cross',
              'foot_row_horizontal', 'foot_row_left', 'foot_row_right', 'foot_row_cross',
              'head_vertical', 'mid_vertical', 'foot_vertical',
              'head_left', 'head_right', 'mid_left', 'mid_right', 'foot_left', 'foot_right',
              'top_divider', 'bottom_divider']:
    setattr(_NO_BORDER, _attr, ' ')
del _attr


# ---------------------------------------------------------------------------
# Location symbols (kept for tests / /map overlay)
# ---------------------------------------------------------------------------

VISUAL_SYMBOLS = {
    "house": "\U0001f3e0",
    "interior": "\U0001f6aa",
    "forest": "\U0001f332",
    "cave": "\U0001f573\ufe0f",
    "village": "\U0001f3d8\ufe0f",
    "city": "\U0001f3d9\ufe0f",
    "dungeon": "\u2694\ufe0f",
    "mountain": "\u26f0\ufe0f",
    "water": "\U0001f30a",
    "road": "\U0001f6e3\ufe0f",
    "ruins": "\U0001f3da\ufe0f",
    "castle": "\U0001f3f0",
    "temple": "\u26e9",
    "camp": "\u26fa",
    "area": "\u25cf",
}


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def get_location_symbol(location) -> str:
    if location.symbol and location.symbol != "?":
        return location.symbol
    return VISUAL_SYMBOLS.get(location.visual_type, "\u25cf")


# ---------------------------------------------------------------------------
# Custom renderables — receive width/height from Rich at render time
# ---------------------------------------------------------------------------

class _WorldMapRenderable:
    """Renders the world map inside a Rich Layout slot."""

    def __init__(self, game: GameState):
        self.game = game

    def __rich_console__(self, console, options):
        w = max(1, options.max_width)
        h = max(1, options.max_height)
        try:
            lines = render_world_map(self.game, w, h)
        except Exception:
            lines = [" " * w] * h
        yield Text("\n".join(lines), no_wrap=True)


class _MinimapRenderable:
    """Renders the minimap inside a Rich Layout slot."""

    def __init__(self, game: GameState):
        self.game = game

    def __rich_console__(self, console, options):
        w = max(1, options.max_width)
        h = max(1, options.max_height)
        try:
            lines = render_minimap(self.game, w, h)
        except Exception:
            lines = [" " * w] * h
        yield Text("\n".join(lines), no_wrap=True)


# ---------------------------------------------------------------------------
# Panel content builders — return Rich renderables (no width parameter)
# ---------------------------------------------------------------------------

def _make_header(game: GameState) -> Panel:
    """Header bar with title, day, time, weather inside a Rich Panel."""
    title = "\u2726 INFINITE RPG"
    day = f"Day {game.world.day}"
    time = game.world.time
    weather = game.world.weather.condition.title()
    temp = f"{game.world.weather.temperature}\u00b0C"

    tbl = Table(show_header=False, box=None, expand=True, padding=0)
    tbl.add_column(justify="left", ratio=1)
    tbl.add_column(justify="right")
    tbl.add_row(
        Text(f" {title} ", style="bold"),
        Text(f"{day} \u2502 {time} \u2502 {weather} {temp}"),
    )
    return Panel(tbl, box=box.SQUARE, expand=True)


def _make_footer() -> Panel:
    """Footer command bar inside a Rich Panel."""
    cmds = " /save  /load  /map  /inventory  /quests  /status  /help  /quit "
    return Panel(Text(cmds), box=box.SQUARE, expand=True)


def _make_location(game: GameState) -> Text:
    location = game.current_location()
    t = Text()
    if not location:
        return t
    t.append(f"  \u25b6 {location.name}\n", style="bold green")
    t.append(f"  {location.description}\n")

    npcs = []
    for npc_id in location.npcs:
        npc = game.world.npcs.get(npc_id)
        if npc and npc.hp > 0:
            npcs.append(npc.name)
    if npcs:
        t.append("  NPCs: ", style="bold yellow")
        t.append(", ".join(npcs) + "\n")

    if location.items:
        t.append("  Items: ", style="bold blue")
        t.append(", ".join(location.items) + "\n")

    interesting = []
    for inter_id in location.interactables:
        inter = game.world.interactables.get(inter_id)
        if inter and inter.state != "default":
            interesting.append(f"{inter.name} [{inter.state}]")
    if interesting:
        t.append("  Object: ", style="magenta")
        t.append(", ".join(interesting) + "\n")
    return t


def _make_narration(game: GameState) -> Text:
    t = Text()
    if not game.last_narration:
        return t
    t.append("  NARRATION\n", style="bold cyan")
    t.append(f"  {game.last_narration}\n")
    return t


def _make_player(game: GameState) -> Text:
    p = game.player
    t = Text()
    t.append("  PLAYER\n", style="bold white")
    hp_bar = render_bar(p.hp, p.max_hp, width=20)
    t.append(render_kv("HP", hp_bar) + "\n")
    t.append(render_kv("LV", str(p.level)) + "\n")
    xp_next = p.level * 100
    xp_bar = render_bar(p.xp, xp_next, width=20)
    t.append(render_kv("XP", xp_bar) + "\n")
    stats = (f"STR:{p.strength} VIT:{p.vitality} "
             f"AGI:{p.agility} INT:{p.intelligence}")
    t.append(render_kv("Stats", stats) + "\n")
    if p.money > 0:
        t.append(render_kv("Gold", str(p.money)) + "\n")
    if p.stat_points > 0:
        t.append(render_kv("Pts", str(p.stat_points)) + "\n")
    return t


def _make_quests(game: GameState) -> Text:
    active = [q for q in game.quests.values() if q.state == "active"]
    t = Text()
    if not active:
        return t
    t.append("  QUESTS\n", style="bold yellow")
    for q in active[:3]:
        total = len(q.objectives)
        done = sum(1 for o in q.objectives if o.completed)
        bar = render_bar(done, total, width=min(12, 20))
        t.append(f"  \u2022 {q.title}  {bar}\n")
        for obj in q.objectives:
            if not obj.completed:
                t.append(f"    \u25cb {obj.description}\n")
    return t


def _make_secondary(game: GameState) -> Text:
    t = Text()
    inv = game.player.inventory
    if inv:
        t.append("  INVENTORY\n", style="bold blue")
        counts: dict[str, int] = {}
        for item in inv:
            counts[item] = counts.get(item, 0) + 1
        parts = []
        for item, count in counts.items():
            parts.append(f"{item}x{count}" if count > 1 else item)
        t.append("  " + ", ".join(parts) + "\n")
    else:
        t.append("  STATUS\n", style="dim")
        t.append("    (extensible)\n", style="dim")
    return t


def _make_future(game: GameState) -> Text:
    t = Text()
    t.append("  SKILLS\n", style="dim")
    t.append("    (coming soon)\n", style="dim")
    return t


# ---------------------------------------------------------------------------
# Layout builder
# ---------------------------------------------------------------------------

def _build_layout(game: GameState, terminal: TerminalSize) -> Layout:
    tw = terminal.width
    th = terminal.height

    header_h = 3   # Panel top + content + Panel bottom
    footer_h = 3
    blank_h = 1    # Blank separator (part of Layout)
    prompt_h = 1   # Reserved but not rendered (caller handles prompt)
    body_height = max(1, th - header_h - footer_h - prompt_h)

    root = Layout(name="root")
    root.split_column(
        Layout(name="header", size=header_h),
        Layout(name="body", size=body_height),
        Layout(name="blank", size=blank_h),
        Layout(name="footer", size=footer_h),
    )

    root["header"].update(_make_header(game))
    root["blank"].update(Text(""))
    root["footer"].update(_make_footer())

    if tw >= MIN_TWO_COLUMN_WIDTH:
        _build_two_column(game, tw, body_height, root)
    else:
        _build_single_column(game, tw, body_height, root)

    return root


def _build_two_column(game: GameState, tw: int, bh: int, root: Layout):
    right_w = max(24, min(int(tw * 0.35), tw // 3))
    left_w = tw - right_w - 1
    left_w = max(40, left_w)
    right_w = tw - left_w - 1

    # Map viewport = body_height - reserved_status_rows
    # Info minimum: location(2) + player(4) + margin(2) = 8 rows
    STATUS_RESERVED_ROWS = 8
    top_h = max(12, bh - STATUS_RESERVED_ROWS)
    bot_h = bh - top_h

    body = Layout(name="body")
    body.split_row(
        Layout(name="left", size=left_w),
        Layout(name="right", size=right_w),
    )

    left = Layout(name="left")
    left.split_column(
        Layout(name="world_map", size=top_h),
        Layout(name="info", size=bot_h),
    )
    left["world_map"].update(_WorldMapRenderable(game))
    left["info"].update(Group(
        _make_location(game),
        _make_narration(game),
        _make_player(game),
        _make_quests(game),
    ))

    right = Layout(name="right")
    right.split_column(
        Layout(name="minimap", size=top_h),
        Layout(name="side", size=bot_h),
    )
    right["minimap"].update(_MinimapRenderable(game))
    right["side"].update(Group(
        _make_secondary(game),
        _make_future(game),
    ))

    body["left"].update(left)
    body["right"].update(right)
    root["body"].update(body)


def _build_single_column(game: GameState, tw: int, bh: int, root: Layout):
    # Give more space to map in single-column mode, especially for smaller terminals
    # Balance: location info needs 2-3 lines, narration needs 1-2 lines, 
    # player/quests needs 2-3 lines, plus a separator
    min_text_h = 7  # Location + description + NPCs + items + separator
    map_h = max(6, bh - min_text_h)  # Ensure at least 6 rows for map (minimum viable viewport)
    text_h = bh - map_h

    content = Group(
        _make_location(game),
        _make_narration(game),
        _make_player(game),
        _make_quests(game),
        Text("\n" + "\u2500" * tw + "\n", style="dim"),
    )

    single = Layout(name="single")
    single.split_column(
        Layout(name="text_content", size=text_h),
        Layout(name="map", size=map_h),
    )
    single["text_content"].update(content)
    single["map"].update(_WorldMapRenderable(game))
    root["body"].update(single)


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def render_game(game: GameState) -> str:
    """Render the complete game screen using Rich-native layout.

    Returns the rendered string (ANSI-coded) with a trailing blank line
    that separates the UI from the input prompt.
    """
    terminal = TerminalSize.detect()
    rich_layout = _build_layout(game, terminal)

    buf = StringIO()
    console = Console(
        file=buf,
        width=terminal.width,
        height=terminal.height,
        force_terminal=True,
        no_color=not colors_enabled(),
    )
    console.print(rich_layout, end="")
    return buf.getvalue()
