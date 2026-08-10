"""Top-down 2D world map for the Infinite RPG (UI V3 - Phase C).

Single underlying map system built on the existing location coordinates
(``map_x`` / ``map_y``), rendered through several views:

  render_world_map()   - local/detail view (top-left panel), player-centered
  render_minimap()     - zoomed-out overview (top-right panel)
  render_full_map()    - full-screen /map overlay

World geometry is deterministic: identical game state always produces an
identical map.  Locations live at their world coordinates, terrain tiles the
gaps, and paths connect neighbouring places.  Every view returns lines that
respect ``visible_width`` so they never overflow the given panel size.
"""

import shutil
from typing import Dict, List, Optional, Tuple

from .state import GameState
from .terminal import (
    visible_width,
    pad_to_width,
    truncate_to_width,
    colorize,
    FG,
)


# ---------------------------------------------------------------------------
# Terrain cell types
# ---------------------------------------------------------------------------

T_GRASS = "."
T_FOREST = "T"
T_PATH = "="
T_BUILDING = "#"
T_WATER = "~"
T_ROCK = "^"
T_DOOR = "+"

# Visual characters rendered for each terrain type (top-down feel)
TERRAIN_CH = {
    T_GRASS: "\u00b7",        # ·  fine grass
    T_FOREST: "\u2593",       # ▓  dark forest canopy
    T_PATH: "\u2500",         # ─  path
    T_BUILDING: "\u25a0",     # ■  building block
    T_WATER: "~",
    T_ROCK: "^",
    T_DOOR: "+",
}

TERRAIN_COLOR = {
    T_GRASS: FG.DIM,
    T_FOREST: FG.GREEN,
    T_PATH: FG.YELLOW,
    T_BUILDING: FG.BRIGHT_WHITE,
    T_WATER: FG.CYAN,
    T_ROCK: FG.DIM,
    T_DOOR: FG.BRIGHT_YELLOW,
}

# Grid resolution in cells per world coordinate unit.
SCALE = 4

# Number of rows reserved at the bottom of the main map view for the
# current-location status line and the legend.
_STATUS_ROWS = 2

# Marker colours + characters
_M_PLAYER = ("@", FG.BRIGHT_GREEN)
_M_VISITED = ("*", FG.YELLOW)
_M_UNVISITED = (None, FG.BRIGHT_WHITE)  # char = location initial
_M_NPC = ("N", FG.BRIGHT_MAGENTA)
_M_ITEM = ("I", FG.BRIGHT_CYAN)
_M_PATH = (".", FG.DIM)

# Where to hang NPC / item markers around a location footprint.
_NPC_OFFSETS = [(2, 0), (-2, 0), (0, 2), (0, -2), (2, -1), (-1, 2)]
_ITEM_OFFSETS = [(-2, 0), (2, 0), (0, -2), (0, 2)]


# ---------------------------------------------------------------------------
# 2-D terrain grid
# ---------------------------------------------------------------------------

class TerrainGrid:
    """A 2-D character grid with terrain data."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.cells = [[T_GRASS] * width for _ in range(height)]
        # Coordinate transforms (set during generation)
        self._ox = 0
        self._oy = 0
        self._scale = SCALE

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def set(self, x: int, y: int, cell_type: str):
        if self.in_bounds(x, y):
            self.cells[y][x] = cell_type

    def get(self, x: int, y: int) -> str:
        if self.in_bounds(x, y):
            return self.cells[y][x]
        return T_GRASS


# ---------------------------------------------------------------------------
# Terrain footprint drawing helpers (all deterministic)
# ---------------------------------------------------------------------------

def _hash2(x: int, y: int, seed: int = 12345) -> int:
    """Deterministic hash of a grid cell position."""
    return (x * 73856093 + y * 19349663 + seed) % 100


_BUILDING_TYPES = {"house", "interior", "village", "city", "dungeon",
                   "castle", "temple", "camp", "ruins", "area"}
_FOREST_TYPES = {"forest", "cave"}


def _draw_struct(grid: TerrainGrid, cx: int, cy: int):
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            grid.set(cx + dx, cy + dy, T_BUILDING)


def _draw_forest(grid: TerrainGrid, cx: int, cy: int):
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            if abs(dx) + abs(dy) > 2:
                continue
            # Leave a few deterministic gaps so it feels like a canopy
            if _hash2(cx + dx, cy + dy, seed=777) > 78:
                continue
            grid.set(cx + dx, cy + dy, T_FOREST)


def _draw_water(grid: TerrainGrid, cx: int, cy: int):
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            grid.set(cx + dx, cy + dy, T_WATER)


def _draw_rock(grid: TerrainGrid, cx: int, cy: int):
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if abs(dx) + abs(dy) <= 1:
                grid.set(cx + dx, cy + dy, T_ROCK)


def _place_door(grid: TerrainGrid, cx: int, cy: int,
                exits: Dict[str, str], locations: dict,
                ox: int, oy: int):
    """Place a door ('+') on the building edge facing its first exit."""
    for target_id in exits.values():
        target = locations.get(target_id)
        if not target:
            continue
        tx = target.map_x * SCALE + ox
        ty = target.map_y * SCALE + oy
        dx = 1 if tx > cx else (-1 if tx < cx else 0)
        dy = 1 if ty > cy else (-1 if ty < cy else 0)
        for ex, ey in ((dx, 0), (0, dy), (dx, dy)):
            if ex == 0 and ey == 0:
                continue
            if grid.in_bounds(cx + ex, cy + ey):
                grid.set(cx + ex, cy + ey, T_DOOR)
                return


def _decorate(grid: TerrainGrid, centers: List[Tuple[int, int]]):
    """Scatter sparse, deterministic water/rock/forest into open land."""
    def isolated(x: int, y: int) -> bool:
        return all(abs(x - cx) + abs(y - cy) > 3 for cx, cy in centers)

    for y in range(grid.height):
        for x in range(grid.width):
            if grid.get(x, y) != T_GRASS or not isolated(x, y):
                continue
            h = _hash2(x, y)
            if h < 4:
                grid.set(x, y, T_WATER)
            elif h < 9:
                grid.set(x, y, T_ROCK)
            elif h < 13:
                grid.set(x, y, T_FOREST)


def _draw_paths(grid: TerrainGrid, game: GameState,
                centers: Dict[str, Tuple[int, int]]):
    """Draw a path between every pair of connected locations."""
    world = game.world
    seen = set()
    for loc in world.locations.values():
        for direction, target_id in loc.exits.items():
            target = world.locations.get(target_id)
            if not target:
                continue
            pair = tuple(sorted((loc.id, target_id)))
            if pair in seen:
                continue
            seen.add(pair)
            x1, y1 = centers[loc.id]
            x2, y2 = centers[target_id]
            cx, cy = x1, y1
            while cx != x2:
                nx = cx + (1 if x2 > cx else -1)
                if grid.in_bounds(nx, cy) and grid.get(nx, cy) == T_GRASS:
                    grid.set(nx, cy, T_PATH)
                cx = nx
            while cy != y2:
                ny = cy + (1 if y2 > cy else -1)
                if grid.in_bounds(cx, ny) and grid.get(cx, ny) == T_GRASS:
                    grid.set(cx, ny, T_PATH)
                cy = ny


# ---------------------------------------------------------------------------
# Grid generation from game state
# ---------------------------------------------------------------------------

def _build_grid(game: GameState) -> TerrainGrid:
    """Create the terrain grid from world locations and their coordinates."""
    world = game.world
    if not world.locations:
        return TerrainGrid(5, 5)

    raw_x = [loc.map_x * SCALE for loc in world.locations.values()]
    raw_y = [loc.map_y * SCALE for loc in world.locations.values()]
    min_x, max_x = min(raw_x), max(raw_x)
    min_y, max_y = min(raw_y), max(raw_y)

    pad = 3
    gw = max_x - min_x + 1 + 2 * pad
    gh = max_y - min_y + 1 + 2 * pad
    grid = TerrainGrid(gw, gh)
    grid._ox = -min_x + pad
    grid._oy = -min_y + pad

    centers: Dict[str, Tuple[int, int]] = {}
    for loc in world.locations.values():
        cx = loc.map_x * SCALE + grid._ox
        cy = loc.map_y * SCALE + grid._oy
        centers[loc.id] = (cx, cy)
        if loc.visual_type in _BUILDING_TYPES:
            _draw_struct(grid, cx, cy)
        elif loc.visual_type in _FOREST_TYPES:
            _draw_forest(grid, cx, cy)
        elif loc.visual_type == "water":
            _draw_water(grid, cx, cy)
        elif loc.visual_type == "mountain":
            _draw_rock(grid, cx, cy)

    # Doors on building edges facing their exit
    for loc in world.locations.values():
        if loc.visual_type in _BUILDING_TYPES and loc.exits and loc.id in centers:
            _place_door(grid, centers[loc.id][0], centers[loc.id][1],
                        loc.exits, world.locations, grid._ox, grid._oy)

    # Sparse terrain variety in open land
    _decorate(grid, list(centers.values()))

    # Paths between connected locations
    _draw_paths(grid, game, centers)

    return grid


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def world_to_grid(game: GameState, grid: TerrainGrid,
                  wx: int, wy: int) -> Tuple[int, int]:
    """Convert world (map_x, map_y) → grid (gx, gy)."""
    return wx * grid._scale + grid._ox, wy * grid._scale + grid._oy


def get_location_grid_pos(game: GameState, grid: TerrainGrid,
                          loc_id: str) -> Tuple[int, int]:
    """Get the grid position for a location id."""
    loc = game.world.locations.get(loc_id)
    if not loc:
        return -1, -1
    return world_to_grid(game, grid, loc.map_x, loc.map_y)


# ---------------------------------------------------------------------------
# Shared marker overlay helper
# ---------------------------------------------------------------------------

def _overlay_markers(game: GameState, grid: TerrainGrid,
                     terrain: List[List[str]], color_grid: List[List[str]],
                     vx: int, vy: int, view_w: int, view_h: int):
    """Overlay location / NPC / item markers into a terrain viewport.

    Player position is reserved first so it always wins.
    """
    px, py = get_location_grid_pos(game, grid, game.player.location)
    pvx, pvy = px - vx, py - vy
    used: set = set()
    if 0 <= pvx < view_w and 0 <= pvy < view_h:
        used.add((pvx, pvy))

    def place(pos: Tuple[int, int], marker: str, color: str,
              target_row: List[str], target_col: List[str]) -> bool:
        if pos in used:
            return False
        if not (0 <= pos[0] < view_w and 0 <= pos[1] < view_h):
            return False
        used.add(pos)
        target_row[pos[1]][pos[0]] = marker
        target_col[pos[1]][pos[0]] = color
        return True

    world = game.world

    # Location markers
    for loc_id, loc in world.locations.items():
        gx, gy = world_to_grid(game, grid, loc.map_x, loc.map_y)
        pos = (gx - vx, gy - vy)
        if (gx - vx, gy - vy) == (pvx, pvy):
            continue  # player covers this cell
        if not (0 <= pos[0] < view_w and 0 <= pos[1] < view_h):
            continue
        if loc_id in game.visited_locations:
            place(pos, "*", _M_VISITED[1], terrain, color_grid)
        else:
            initial = loc.name[0].upper()
            place(pos, initial, _M_UNVISITED[1], terrain, color_grid)

    # NPC markers
    for npc in world.npcs.values():
        base = world.locations.get(npc.location)
        if not base:
            continue
        gx, gy = world_to_grid(game, grid, base.map_x, base.map_y)
        for dx, dy in _NPC_OFFSETS:
            if place((gx - vx + dx, gy - vy + dy), "N", _M_NPC[1],
                     terrain, color_grid):
                break

    # Item / POI markers (one per location that has items)
    for loc in world.locations.values():
        if not loc.items:
            continue
        gx, gy = world_to_grid(game, grid, loc.map_x, loc.map_y)
        for dx, dy in _ITEM_OFFSETS:
            if place((gx - vx + dx, gy - vy + dy), "I", _M_ITEM[1],
                     terrain, color_grid):
                break

    # Player marker always wins
    if 0 <= pvx < view_w and 0 <= pvy < view_h:
        terrain[pvy][pvx] = "@"
        color_grid[pvy][pvx] = FG.BRIGHT_GREEN


def _compose_lines(terrain: List[List[str]], color_grid: List[List[str]],
                   width: int) -> List[str]:
    """Turn the coloured terrain cells into width-aligned text lines."""
    lines = []
    for row in range(len(terrain)):
        parts = []
        for col in range(len(terrain[row])):
            ch = terrain[row][col]
            c = color_grid[row][col]
            parts.append(colorize(ch, c) if c else ch)
        lines.append(pad_to_width("".join(parts), width))
    return lines


# ---------------------------------------------------------------------------
# Main world map (local / detail view, player-centered)
# ---------------------------------------------------------------------------

def render_world_map(game: GameState, width: int, height: int) -> List[str]:
    """Render a local 2-D world map centered on the player.

    Returns exactly *height* lines, each exactly *width* visible chars.
    """
    grid = _build_grid(game)
    world = game.world
    if not world.locations:
        return [pad_to_width("", width)] * max(0, height)

    px, py = get_location_grid_pos(game, grid, game.player.location)
    px = max(0, min(px, grid.width - 1))
    py = max(0, min(py, grid.height - 1))

    # Calculate viewport size based on available space
    # Reserve minimal space for status/legend: 1 line for status, 1 line for legend
    status_height = 2
    min_view_h = 6  # Minimum viable map height
    min_view_w = 12  # Minimum viable map width
    
    # Base viewport size - use most of the panel space
    view_h = max(min_view_h, height - status_height)
    view_w = max(min_view_w, width - 2)
    
    # Cap at grid dimensions (show as much world as fits)
    view_h = min(grid.height, view_h)
    view_w = min(grid.width, view_w)

    # Camera: keep the player centered
    vx = max(0, min(px - view_w // 2, max(0, grid.width - view_w)))
    vy = max(0, min(py - view_h // 2, max(0, grid.height - view_h)))

    terrain = []
    color_grid = []
    for r in range(view_h):
        t_row = []
        c_row = []
        for c in range(view_w):
            gx, gy = vx + c, vy + r
            ch = grid.get(gx, gy)
            t_row.append(TERRAIN_CH.get(ch, ch))
            c_row.append(TERRAIN_COLOR.get(ch, ""))
        terrain.append(t_row)
        color_grid.append(c_row)

    _overlay_markers(game, grid, terrain, color_grid, vx, vy, view_w, view_h)

    lines = _compose_lines(terrain, color_grid, width)

    while len(lines) < height:
        lines.append(pad_to_width("", width))

    current = world.locations.get(game.player.location)
    if current and height > view_h:
        status = f"\u25c9 {current.name}"
        lines[view_h] = pad_to_width(
            truncate_to_width(colorize(status, FG.BRIGHT_GREEN), width), width)
    if height > view_h + 1:
        legend = "@You  *Visited  N:NPC  I:Item"
        if width < 26:
            legend = "@You *Vis N I"
        if width < 12:
            legend = "@*NI"
        lines[view_h + 1] = pad_to_width(legend, width)

    return lines[:height]


# ---------------------------------------------------------------------------
# Minimap (zoomed-out overview)
# ---------------------------------------------------------------------------

def render_minimap(game: GameState, width: int, height: int) -> List[str]:
    """Render a zoomed-out minimap showing the whole world.

    Returns exactly *height* lines, each exactly *width* visible chars.
    Uses nearly all available space for the map, with minimal legend area.
    """
    world = game.world
    if not world.locations:
        return [pad_to_width("(empty)", width)] + \
               [pad_to_width("", width)] * (max(0, height) - 1)

    xs = [loc.map_x for loc in world.locations.values()]
    ys = [loc.map_y for loc in world.locations.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(1, max_x - min_x)
    span_y = max(1, max_y - min_y)

    # Use most of the available space for the map content
    # Leave minimal margins for readability
    inner_w = max(3, width - 2)
    # Reserve at least one row for legend, possibly more if needed for compactness
    map_rows = max(3, height - 1)  # Always show map with legend below

    def scale_coord(wx: int, wy: int) -> Tuple[int, int]:
        mx = int(round((wx - min_x) / span_x * (inner_w - 1)))
        my = int(round((wy - min_y) / span_y * (map_rows - 1)))
        return max(0, min(mx, inner_w - 1)), max(0, min(my, map_rows - 1))

    positions = {loc_id: scale_coord(loc.map_x, loc.map_y)
                 for loc_id, loc in world.locations.items()}

    buff: List[List[Tuple[str, str]]] = \
        [[(" ", "")] * inner_w for _ in range(map_rows)]

    # Connection lines
    seen = set()
    for loc in world.locations.values():
        for direction, target_id in loc.exits.items():
            target = world.locations.get(target_id)
            if not target:
                continue
            pair = tuple(sorted((loc.id, target_id)))
            if pair in seen:
                continue
            seen.add(pair)
            x1, y1 = positions[loc.id]
            x2, y2 = positions[target_id]
            steps = max(abs(x2 - x1), abs(y2 - y1), 1)
            for s in range(1, steps):
                ix = x1 + (x2 - x1) * s // steps
                iy = y1 + (y2 - y1) * s // steps
                if buff[iy][ix][0] == " ":
                    buff[iy][ix] = _M_PATH

    # Location markers
    for loc_id, loc in world.locations.items():
        mx, my = positions[loc_id]
        is_cur = loc_id == game.player.location
        is_vis = loc_id in game.visited_locations
        if is_cur:
            cell = _M_PLAYER
        elif is_vis:
            cell = _M_VISITED
        else:
            cell = (loc.name[0].upper(), _M_UNVISITED[1])
        buff[my][mx] = cell

    lines = []
    for row in range(map_rows):
        parts = [colorize(ch, c) if c else ch for ch, c in buff[row]]
        lines.append(pad_to_width("".join(parts), width))

    # Compact legend - use only essential symbols
    legend = "@You *Vis"
    if width < 10:
        legend = "@*"
    while len(lines) < max(0, height - 1):
        lines.append(pad_to_width("", width))
    if height >= 1:
        lines.append(pad_to_width(legend, width))

    while len(lines) < max(0, height):
        lines.append(pad_to_width("", width))
    return lines[:height]


# ---------------------------------------------------------------------------
# Full-screen /map overlay
# ---------------------------------------------------------------------------

def render_full_map(game: GameState, width: Optional[int] = None) -> str:
    """Render the full-screen world map for the /map command.

    Uses the same terrain grid as the local view, showing the whole world
    with location labels.
    """
    if width is None:
        width = shutil.get_terminal_size(fallback=(80, 24)).columns
    width = max(24, width)

    grid = _build_grid(game)
    world = game.world
    if not world.locations:
        return "\u2726 Top-Down World Map \u2726\n\n(empty world)"

    px, py = get_location_grid_pos(game, grid, game.player.location)

    loc_info = {}
    for loc_id, loc in world.locations.items():
        gx, gy = world_to_grid(game, grid, loc.map_x, loc.map_y)
        is_cur = loc_id == game.player.location
        is_vis = loc_id in game.visited_locations
        loc_info[(gx, gy)] = (loc.name, is_cur, is_vis)

    lines = []
    title = " \u2726 TOP-DOWN WORLD MAP \u2726 "
    lines.append(" " * max(0, (width - len(title)) // 2) + title)
    lines.append("")

    for gy in range(grid.height):
        row_str = "  "
        gx = 0
        while gx < grid.width:
            if (gx, gy) == (px, py):
                row_str += colorize("@", FG.BRIGHT_GREEN, FG.BOLD)
                gx += 1
                continue
            if (gx, gy) in loc_info:
                name, is_cur, is_vis = loc_info[(gx, gy)]
                if is_cur:
                    pre, post, col = "[", "]", FG.BRIGHT_GREEN
                elif is_vis:
                    pre, post, col = "(", ")", FG.YELLOW
                else:
                    pre, post, col = " ", "", FG.BRIGHT_WHITE
                row_str += colorize(pre + name + post, col)
                gx += len(name) + len(pre) + len(post)
                continue
            ch = grid.get(gx, gy)
            tc = TERRAIN_CH.get(ch, ch)
            cc = TERRAIN_COLOR.get(ch, "")
            row_str += colorize(tc, cc) if cc else tc
            gx += 1
        lines.append(row_str)

    lines.append("")
    lines.append("  Legend: " + colorize("@", FG.BRIGHT_GREEN) + " You  "
                 + colorize("*", FG.YELLOW) + " Visited  "
                 + colorize("N", FG.BRIGHT_MAGENTA) + " NPC  "
                 + colorize("I", FG.BRIGHT_CYAN) + " Item  "
                 + colorize("\u2593", FG.GREEN) + " Forest  "
                 + colorize("\u2500", FG.YELLOW) + " Path")
    lines.append("")

    return "\n".join(lines)