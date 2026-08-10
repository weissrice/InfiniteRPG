"""Local map generation for existing world locations.

Creates walkable tile grids for each location, with terrain, collision,
objects, exit points, and spawn positions.

This module only generates data. It does not handle movement, rendering,
or input.
"""

from __future__ import annotations

from .state import ExitPoint, LocalMap, LocalObject, Location

# Standard map dimensions
MAP_WIDTH = 19
MAP_HEIGHT = 11

# Terrain characters
T_FLOOR = "."
T_WALL = "#"
T_TREE = "T"
T_PATH = "="
T_DOOR = "+"
T_COUNTER = "C"
T_TABLE = "TBL"
T_CHAIR = "c"
T_FIREPLACE = "F"
T_SHELF = "S"
T_BED = "B"
T_CABINET = "K"
T_STOVE = "ST"
T_SINK = "SN"
T_RAILING = "R"


def _make_grid(width: int, height: int, fill: str) -> list[list[str]]:
    """Create a 2D grid filled with a single character."""
    return [[fill for _ in range(width)] for _ in range(height)]


def _make_collision(width: int, height: int, fill: bool) -> list[list[bool]]:
    """Create a 2D collision grid filled with a single value."""
    return [[fill for _ in range(width)] for _ in range(height)]


def _set_rect(grid: list[list[str]], x: int, y: int, w: int, h: int, ch: str) -> None:
    """Fill a rectangle in a grid."""
    for row in range(y, y + h):
        for col in range(x, x + w):
            if 0 <= row < len(grid) and 0 <= col < len(grid[0]):
                grid[row][col] = ch


def _set_rect_collision(collision: list[list[bool]], x: int, y: int,
                         w: int, h: int, blocked: bool) -> None:
    """Fill a rectangle in a collision grid."""
    for row in range(y, y + h):
        for col in range(x, x + w):
            if 0 <= row < len(collision) and 0 <= col < len(collision[0]):
                collision[row][col] = blocked


def _add_walls(terrain: list[list[str]], collision: list[list[bool]]) -> None:
    """Add border walls to a map."""
    w = len(terrain[0])
    h = len(terrain)
    for x in range(w):
        terrain[0][x] = T_WALL
        collision[0][x] = True
        terrain[h - 1][x] = T_WALL
        collision[h - 1][x] = True
    for y in range(h):
        terrain[y][0] = T_WALL
        collision[y][0] = True
        terrain[y][w - 1] = T_WALL
        collision[y][w - 1] = True


def _is_walkable(terrain: list[list[str]], x: int, y: int) -> bool:
    """Check if a tile is walkable (not a wall)."""
    if y < 0 or y >= len(terrain) or x < 0 or x >= len(terrain[0]):
        return False
    return terrain[y][x] != T_WALL


# ---------------------------------------------------------------------------
# Interior maps
# ---------------------------------------------------------------------------

def _generate_living_room() -> LocalMap:
    """Generate the Old Wooden House / Living Room local map."""
    w, h = MAP_WIDTH, MAP_HEIGHT
    terrain = _make_grid(w, h, T_FLOOR)
    collision = _make_collision(w, h, False)
    objects: list[LocalObject] = []

    # Border walls
    _add_walls(terrain, collision)

    # Fireplace on the north wall (center-left)
    objects.append(LocalObject(
        id="fireplace", name="Fireplace", x=5, y=1,
        tile="F", blocking=True, width=2, height=1,
    ))
    terrain[1][5] = "F"
    collision[1][5] = True
    terrain[1][6] = "F"
    collision[1][6] = True

    # Table in the center area
    objects.append(LocalObject(
        id="table", name="Table", x=8, y=5,
        tile="T", blocking=True, width=3, height=2,
    ))
    _set_rect(terrain, 8, 5, 3, 2, "T")
    _set_rect_collision(collision, 8, 5, 3, 2, True)

    # Chairs around the table (non-blocking)
    objects.append(LocalObject(
        id="chair_north", name="Chair", x=9, y=4,
        tile="c", blocking=False, width=1, height=1,
    ))
    terrain[4][9] = "c"
    objects.append(LocalObject(
        id="chair_south", name="Chair", x=9, y=7,
        tile="c", blocking=False, width=1, height=1,
    ))
    terrain[7][9] = "c"

    # Cabinet along the south wall
    objects.append(LocalObject(
        id="cabinet", name="Cabinet", x=2, y=9,
        tile="K", blocking=True, width=4, height=1,
    ))
    _set_rect(terrain, 2, 9, 4, 1, "K")
    _set_rect_collision(collision, 2, 9, 4, 1, True)

    # Couch along the west wall (shifted up to not block kitchen exit at (0,5))
    objects.append(LocalObject(
        id="couch", name="Couch", x=1, y=3,
        tile="S", blocking=True, width=1, height=2,
    ))
    terrain[3][1] = "S"
    terrain[4][1] = "S"
    collision[3][1] = True
    collision[4][1] = True

    # Railing near the upstairs exit (shifted right to not block exit at (10,0))
    objects.append(LocalObject(
        id="railing", name="Railing", x=11, y=1,
        tile="R", blocking=True, width=1, height=1,
    ))
    terrain[1][11] = "R"
    collision[1][11] = True

    # Exits
    exits = {
        "kitchen": ExitPoint(x=0, y=5, target_location_id="kitchen", entry_name="outside"),
        "outside": ExitPoint(x=18, y=5, target_location_id="forest_edge", entry_name="house"),
        "upstairs": ExitPoint(x=10, y=0, target_location_id="upstairs", entry_name="downstairs"),
    }

    # Make exit tiles walkable
    for ep in exits.values():
        terrain[ep.y][ep.x] = T_DOOR
        collision[ep.y][ep.x] = False

    return LocalMap(
        width=w, height=h,
        terrain=terrain, collision=collision,
        objects=objects, exits=exits,
        spawn=[12, 5],
    )


def _generate_kitchen() -> LocalMap:
    """Generate the Kitchen local map."""
    w, h = MAP_WIDTH, MAP_HEIGHT
    terrain = _make_grid(w, h, T_FLOOR)
    collision = _make_collision(w, h, False)
    objects: list[LocalObject] = []

    _add_walls(terrain, collision)

    # Counter along the north wall
    objects.append(LocalObject(
        id="counter_north", name="Counter", x=2, y=1,
        tile="C", blocking=True, width=8, height=1,
    ))
    _set_rect(terrain, 2, 1, 8, 1, "C")
    _set_rect_collision(collision, 2, 1, 8, 1, True)

    # Stove on the north wall
    objects.append(LocalObject(
        id="stove", name="Stove", x=11, y=1,
        tile="ST", blocking=True, width=1, height=1,
    ))
    terrain[1][11] = "ST"
    collision[1][11] = True

    # Sink on the north wall
    objects.append(LocalObject(
        id="sink", name="Sink", x=13, y=1,
        tile="SN", blocking=True, width=1, height=1,
    ))
    terrain[1][13] = "SN"
    collision[1][13] = True

    # Cabinet along the west wall
    objects.append(LocalObject(
        id="cabinet_west", name="Cabinet", x=1, y=3,
        tile="K", blocking=True, width=1, height=2,
    ))
    terrain[3][1] = "K"
    terrain[4][1] = "K"
    collision[3][1] = True
    collision[4][1] = True

    # Table in the center-south
    objects.append(LocalObject(
        id="kitchen_table", name="Table", x=8, y=6,
        tile="T", blocking=True, width=3, height=2,
    ))
    _set_rect(terrain, 8, 6, 3, 2, "T")
    _set_rect_collision(collision, 8, 6, 3, 2, True)

    # Shelf along the south wall
    objects.append(LocalObject(
        id="shelf", name="Shelf", x=2, y=9,
        tile="S", blocking=True, width=5, height=1,
    ))
    _set_rect(terrain, 2, 9, 5, 1, "S")
    _set_rect_collision(collision, 2, 9, 5, 1, True)

    # Exit
    exits = {
        "outside": ExitPoint(x=18, y=5, target_location_id="old_wooden_house", entry_name="kitchen"),
    }

    for ep in exits.values():
        terrain[ep.y][ep.x] = T_DOOR
        collision[ep.y][ep.x] = False

    return LocalMap(
        width=w, height=h,
        terrain=terrain, collision=collision,
        objects=objects, exits=exits,
        spawn=[10, 5],
    )


def _generate_upstairs() -> LocalMap:
    """Generate the Upstairs Hallway local map."""
    w, h = MAP_WIDTH, MAP_HEIGHT
    terrain = _make_grid(w, h, T_FLOOR)
    collision = _make_collision(w, h, False)
    objects: list[LocalObject] = []

    _add_walls(terrain, collision)

    # Railing along the south side (shifted right to not block downstairs exit at (9,10))
    objects.append(LocalObject(
        id="stair_railing", name="Stair Railing", x=10, y=9,
        tile="R", blocking=True, width=5, height=1,
    ))
    _set_rect(terrain, 10, 9, 5, 1, "R")
    _set_rect_collision(collision, 10, 9, 5, 1, True)

    # Doors along the north wall (old doors)
    objects.append(LocalObject(
        id="door_north_1", name="Old Door", x=4, y=1,
        tile="+", blocking=True, width=1, height=1,
    ))
    terrain[1][4] = "+"
    collision[1][4] = True

    objects.append(LocalObject(
        id="door_north_2", name="Old Door", x=8, y=1,
        tile="+", blocking=True, width=1, height=1,
    ))
    terrain[1][8] = "+"
    collision[1][8] = True

    # Locked door at the far end (east)
    objects.append(LocalObject(
        id="locked_door", name="Locked Upstairs Door", x=17, y=5,
        tile="+", blocking=True,
        interactable_id="locked_upstairs_door", width=1, height=1,
    ))
    terrain[5][17] = "+"
    collision[5][17] = True

    # Small table in the hallway
    objects.append(LocalObject(
        id="hall_table", name="Small Table", x=5, y=5,
        tile="T", blocking=True, width=1, height=1,
    ))
    terrain[5][5] = "T"
    collision[5][5] = True

    # Cabinet along the west wall
    objects.append(LocalObject(
        id="hall_cabinet", name="Cabinet", x=1, y=3,
        tile="K", blocking=True, width=1, height=1,
    ))
    terrain[3][1] = "K"
    collision[3][1] = True

    # Exit
    exits = {
        "downstairs": ExitPoint(x=9, y=10, target_location_id="old_wooden_house", entry_name="upstairs"),
    }

    for ep in exits.values():
        terrain[ep.y][ep.x] = T_DOOR
        collision[ep.y][ep.x] = False

    return LocalMap(
        width=w, height=h,
        terrain=terrain, collision=collision,
        objects=objects, exits=exits,
        spawn=[9, 8],
    )


# ---------------------------------------------------------------------------
# Outdoor maps
# ---------------------------------------------------------------------------

def _seed_hash(x: int, y: int, seed: int = 42) -> int:
    """Deterministic hash for scatter placement."""
    return (x * 73856093 + y * 19349663 + seed) % 100


def _generate_forest_edge() -> LocalMap:
    """Generate the Forest Edge local map."""
    w, h = MAP_WIDTH, MAP_HEIGHT
    terrain = _make_grid(w, h, T_FLOOR)
    collision = _make_collision(w, h, False)
    objects: list[LocalObject] = []

    # Border: top and bottom rows are trees
    for x in range(w):
        terrain[0][x] = T_TREE
        collision[0][x] = True
        terrain[h - 1][x] = T_TREE
        collision[h - 1][x] = True

    # Left and right borders: trees
    for y in range(h):
        terrain[y][0] = T_TREE
        collision[y][0] = True
        terrain[y][w - 1] = T_TREE
        collision[y][w - 1] = True

    # Scatter trees across the map (deterministic)
    tree_count = 0
    for y in range(2, h - 2):
        for x in range(2, w - 2):
            h_val = _seed_hash(x, y, seed=100)
            if h_val < 12 and tree_count < 18:
                terrain[y][x] = T_TREE
                collision[y][x] = True
                tree_count += 1

    # Path from house exit (west) to forest exit (east)
    path_y = 5
    for x in range(1, w - 1):
        if terrain[path_y][x] == T_TREE:
            terrain[path_y][x] = T_PATH
            collision[path_y][x] = False
        if terrain[path_y - 1][x] == T_TREE:
            terrain[path_y - 1][x] = T_PATH
            collision[path_y - 1][x] = False

    # Clear area near the center for the merchant
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            cx, cy = 10 + dx, 5 + dy
            if 0 <= cx < w and 0 <= cy < h:
                if terrain[cy][cx] == T_TREE:
                    terrain[cy][cx] = T_FLOOR
                    collision[cy][cx] = False

    # A few rocks for variety
    objects.append(LocalObject(
        id="rock_1", name="Rock", x=7, y=3,
        tile="^", blocking=True, width=1, height=1,
    ))
    terrain[3][7] = "^"
    collision[3][7] = True

    objects.append(LocalObject(
        id="rock_2", name="Rock", x=14, y=7,
        tile="^", blocking=True, width=1, height=1,
    ))
    terrain[7][14] = "^"
    collision[7][14] = True

    # Exits
    exits = {
        "house": ExitPoint(x=0, y=5, target_location_id="old_wooden_house", entry_name="outside"),
        "forest": ExitPoint(x=18, y=5, target_location_id="deep_forest", entry_name="back"),
    }

    # Make exit tiles walkable
    for ep in exits.values():
        terrain[ep.y][ep.x] = T_DOOR
        collision[ep.y][ep.x] = False

    return LocalMap(
        width=w, height=h,
        terrain=terrain, collision=collision,
        objects=objects, exits=exits,
        spawn=[2, 5],
    )


def _generate_deep_forest() -> LocalMap:
    """Generate the Deep Forest local map."""
    w, h = MAP_WIDTH, MAP_HEIGHT
    terrain = _make_grid(w, h, T_TREE)
    collision = _make_collision(w, h, True)
    objects: list[LocalObject] = []

    # Border: all trees (already set by init)

    # Clear a winding path from west entrance into the forest
    path_points = [
        (0, 5), (1, 5), (2, 5), (3, 5), (4, 5),
        (4, 4), (4, 3), (5, 3), (6, 3), (7, 3),
        (7, 4), (7, 5), (7, 6), (7, 7),
        (8, 7), (9, 7), (10, 7),
        (10, 6), (10, 5), (10, 4),
        (11, 4), (12, 4), (13, 4),
        (13, 5), (13, 6), (14, 6), (15, 6),
        (15, 5), (15, 4), (15, 3),
        (16, 3), (16, 4), (16, 5),
    ]
    for px, py in path_points:
        if 0 <= px < w and 0 <= py < h:
            terrain[py][px] = T_PATH
            collision[py][px] = False

    # Clear some small clearings
    clearings = [(5, 5), (9, 5), (12, 5)]
    for cx, cy in clearings:
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h:
                    if terrain[ny][nx] == T_TREE:
                        terrain[ny][nx] = T_FLOOR
                        collision[ny][nx] = False

    # A few rocks
    objects.append(LocalObject(
        id="boulder_1", name="Boulder", x=6, y=6,
        tile="^", blocking=True, width=1, height=1,
    ))
    if terrain[6][6] != T_PATH:
        terrain[6][6] = "^"
        collision[6][6] = True

    objects.append(LocalObject(
        id="boulder_2", name="Boulder", x=14, y=3,
        tile="^", blocking=True, width=1, height=1,
    ))
    if terrain[3][14] != T_PATH:
        terrain[3][14] = "^"
        collision[3][14] = True

    # Stump for variety
    objects.append(LocalObject(
        id="stump", name="Tree Stump", x=11, y=6,
        tile="T", blocking=True, width=1, height=1,
    ))
    if terrain[6][11] != T_PATH:
        terrain[6][11] = "T"
        collision[6][11] = True

    # Exit
    exits = {
        "back": ExitPoint(x=0, y=5, target_location_id="forest_edge", entry_name="forest"),
    }

    for ep in exits.values():
        terrain[ep.y][ep.x] = T_DOOR
        collision[ep.y][ep.x] = False

    return LocalMap(
        width=w, height=h,
        terrain=terrain, collision=collision,
        objects=objects, exits=exits,
        spawn=[1, 5],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Map from location visual_type / id to generator function
_INTERIOR_GENERATORS = {
    "old_wooden_house": _generate_living_room,
    "kitchen": _generate_kitchen,
    "upstairs": _generate_upstairs,
}

_OUTDOOR_GENERATORS = {
    "forest_edge": _generate_forest_edge,
    "deep_forest": _generate_deep_forest,
}


def generate_local_map(location: Location) -> LocalMap:
    """Generate a default local map for a location.

    Uses the location's id and visual_type to select an appropriate
    generator. Returns a fully-formed LocalMap with terrain, collision,
    objects, exits, and spawn.
    """
    if location.id in _INTERIOR_GENERATORS:
        return _INTERIOR_GENERATORS[location.id]()

    if location.id in _OUTDOOR_GENERATORS:
        return _OUTDOOR_GENERATORS[location.id]()

    # For AI-generated locations, use visual_type to choose generator
    visual = location.visual_type.lower() if location.visual_type else ""
    interior_types = {
        "interior", "house", "building", "dungeon", "cave",
        "room", "hall", "tower", "basement", "attic",
        "tunnel", "corridor", "chamber", "crypt",
    }
    if visual in interior_types:
        return _generate_generic_interior(location)

    return _generate_generic_outdoor(location)


def validate_local_map(
    lm: LocalMap,
    npcs: list | None = None,
    interactables: list | None = None,
    location_id: str | None = None,
) -> bool:
    """Validate a LocalMap for correctness.

    Returns True if the map is valid (all exits reachable, no overlaps, etc.).
    Optionally validates NPC and Interactable positions.

    When *location_id* is supplied, only NPCs and interactables whose
    ``.location`` matches are validated against this map.  NPCs and
    interactables belonging to other locations are ignored, since their
    local coordinates are relative to a different map.
    """
    from collections import deque

    # Basic dimension checks
    if lm.width < 5 or lm.height < 5:
        return False
    if len(lm.terrain) != lm.height:
        return False
    for row in lm.terrain:
        if len(row) != lm.width:
            return False
    if len(lm.collision) != lm.height:
        return False

    # Spawn validity
    sx, sy = lm.spawn
    if not (0 <= sx < lm.width and 0 <= sy < lm.height):
        return False
    if lm.collision[sy][sx]:
        return False

    # Exit validity
    for ename, ep in lm.exits.items():
        if not (0 <= ep.x < lm.width and 0 <= ep.y < lm.height):
            return False
        if lm.collision[ep.y][ep.x]:
            return False
        if not ep.target_location_id:
            return False

    # Object footprint validity
    for obj in lm.objects:
        if obj.width < 1 or obj.height < 1:
            return False
        if obj.x < 0 or obj.y < 0:
            return False
        if obj.x + obj.width > lm.width or obj.y + obj.height > lm.height:
            return False
        if obj.blocking:
            for dy in range(obj.height):
                for dx in range(obj.width):
                    if not lm.collision[obj.y + dy][obj.x + dx]:
                        return False

    # No blocking object overlaps an exit
    for obj in lm.objects:
        if not obj.blocking:
            continue
        for ep in lm.exits.values():
            if obj.x <= ep.x < obj.x + obj.width and obj.y <= ep.y < obj.y + obj.height:
                return False

    # BFS reachability from spawn
    visited = set()
    queue = deque([(sx, sy)])
    visited.add((sx, sy))
    while queue:
        cx, cy = queue.popleft()
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < lm.width and 0 <= ny < lm.height:
                if (nx, ny) not in visited and not lm.collision[ny][nx]:
                    visited.add((nx, ny))
                    queue.append((nx, ny))

    # All exits must be reachable
    for ename, ep in lm.exits.items():
        if (ep.x, ep.y) not in visited:
            return False

    # NPC position validation
    exit_positions = {(ep.x, ep.y) for ep in lm.exits.values()}
    blocking_tiles: set[tuple[int, int]] = set()
    for obj in lm.objects:
        if obj.blocking:
            for dy in range(obj.height):
                for dx in range(obj.width):
                    blocking_tiles.add((obj.x + dx, obj.y + dy))

    if npcs is not None:
        npc_positions: set[tuple[int, int]] = set()
        for npc in npcs:
            if location_id is not None and npc.location != location_id:
                continue
            if npc.local_x < 0 or npc.local_y < 0:
                continue
            nx, ny = npc.local_x, npc.local_y
            if not (0 <= nx < lm.width and 0 <= ny < lm.height):
                return False
            if lm.collision[ny][nx]:
                return False
            if (nx, ny) in blocking_tiles:
                return False
            if (nx, ny) in exit_positions:
                return False
            if (nx, ny) in npc_positions:
                return False
            npc_positions.add((nx, ny))

    # Interactable position validation
    if interactables is not None:
        all_occupied = set()
        if npcs is not None:
            all_occupied |= {(n.local_x, n.local_y)
                             for n in npcs
                             if n.local_x >= 0
                             and (location_id is None or n.location == location_id)}
        for inter in interactables:
            if location_id is not None and inter.location != location_id:
                continue
            if inter.local_x < 0 or inter.local_y < 0:
                continue
            ix, iy = inter.local_x, inter.local_y
            if not (0 <= ix < lm.width and 0 <= iy < lm.height):
                return False
            if lm.collision[iy][ix]:
                return False
            if (ix, iy) in blocking_tiles:
                return False
            if (ix, iy) in exit_positions:
                return False
            if (ix, iy) in all_occupied:
                return False
            all_occupied.add((ix, iy))

    return True


def _generate_generic_interior(location: Location) -> LocalMap:
    """Generate a generic interior map for unknown locations.

    Creates a room with walls, a door for each exit, and basic furniture.
    Exit placement is based on the location's world-graph exits.
    """
    w, h = MAP_WIDTH, MAP_HEIGHT
    terrain = _make_grid(w, h, T_FLOOR)
    collision = _make_collision(w, h, False)
    objects: list[LocalObject] = []

    _add_walls(terrain, collision)

    # Place exits on borders based on location's world-graph exits
    exit_positions = _compute_exit_positions(location, w, h)
    exits = {}
    for exit_name, (ex, ey) in exit_positions.items():
        target_id = location.exits.get(exit_name, "")
        entry_name = _guess_entry_name(exit_name)
        exits[exit_name] = ExitPoint(
            x=ex, y=ey,
            target_location_id=target_id,
            entry_name=entry_name,
        )
        terrain[ey][ex] = T_DOOR
        collision[ey][ex] = False

    # Add a small table in the center (non-blocking for walkability)
    table_x = w // 2 - 1
    table_y = h // 2
    if not collision[table_y][table_x]:
        objects.append(LocalObject(
            id="table", name="Table", x=table_x, y=table_y,
            tile="T", blocking=False, width=1, height=1,
        ))
        terrain[table_y][table_x] = "T"

    # Spawn at center, offset if blocked
    spawn_x, spawn_y = w // 2, h // 2
    if collision[spawn_y][spawn_x]:
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                nx, ny = spawn_x + dx, spawn_y + dy
                if 0 <= nx < w and 0 <= ny < h and not collision[ny][nx]:
                    spawn_x, spawn_y = nx, ny
                    break
            else:
                continue
            break

    return LocalMap(
        width=w, height=h,
        terrain=terrain, collision=collision,
        objects=objects, exits=exits,
        spawn=[spawn_x, spawn_y],
    )


def _generate_generic_outdoor(location: Location) -> LocalMap:
    """Generate a generic outdoor map for unknown locations.

    Creates an open area with a path, scattered trees/rocks, and exits.
    """
    w, h = MAP_WIDTH, MAP_HEIGHT
    terrain = _make_grid(w, h, T_FLOOR)
    collision = _make_collision(w, h, False)
    objects: list[LocalObject] = []

    # Border walls (trees for outdoor)
    for x in range(w):
        terrain[0][x] = T_TREE
        collision[0][x] = True
        terrain[h - 1][x] = T_TREE
        collision[h - 1][x] = True
    for y in range(h):
        terrain[y][0] = T_TREE
        collision[y][0] = True
        terrain[y][w - 1] = T_TREE
        collision[y][w - 1] = True

    # Scatter a few trees deterministically
    tree_count = 0
    for y in range(2, h - 2):
        for x in range(2, w - 2):
            h_val = _seed_hash(x, y, seed=hash(location.id) % 10000)
            if h_val < 10 and tree_count < 8:
                terrain[y][x] = T_TREE
                collision[y][x] = True
                tree_count += 1

    # Central path
    path_y = h // 2
    for x in range(1, w - 1):
        if terrain[path_y][x] == T_TREE:
            terrain[path_y][x] = T_PATH
            collision[path_y][x] = False

    # Place exits on borders
    exit_positions = _compute_exit_positions(location, w, h)
    exits = {}
    for exit_name, (ex, ey) in exit_positions.items():
        target_id = location.exits.get(exit_name, "")
        entry_name = _guess_entry_name(exit_name)
        exits[exit_name] = ExitPoint(
            x=ex, y=ey,
            target_location_id=target_id,
            entry_name=entry_name,
        )
        terrain[ey][ex] = T_DOOR
        collision[ey][ex] = False
        # Clear path to exit
        if ey == 0:
            for cy in range(1, path_y + 1):
                if terrain[cy][ex] == T_TREE:
                    terrain[cy][ex] = T_PATH
                    collision[cy][ex] = False
        elif ey == h - 1:
            for cy in range(path_y, h - 1):
                if terrain[cy][ex] == T_TREE:
                    terrain[cy][ex] = T_PATH
                    collision[cy][ex] = False
        elif ex == 0:
            for cx in range(1, w // 2 + 1):
                if terrain[ey][cx] == T_TREE:
                    terrain[ey][cx] = T_PATH
                    collision[ey][cx] = False
        elif ex == w - 1:
            for cx in range(w // 2, w - 1):
                if terrain[ey][cx] == T_TREE:
                    terrain[ey][cx] = T_PATH
                    collision[ey][cx] = False

    # A few rocks
    rock_seed = hash(location.id) % 10000
    for i in range(2):
        rx = 3 + (rock_seed + i * 7) % (w - 6)
        ry = 3 + (rock_seed + i * 13) % (h - 6)
        if not collision[ry][rx] and terrain[ry][rx] == T_FLOOR:
            objects.append(LocalObject(
                id="rock_%d" % (i + 1), name="Rock", x=rx, y=ry,
                tile="^", blocking=True, width=1, height=1,
            ))
            terrain[ry][rx] = "^"
            collision[ry][rx] = True

    # Spawn on path
    spawn_x, spawn_y = w // 2, path_y
    if collision[spawn_y][spawn_x]:
        for dx in range(-2, 3):
            nx = spawn_x + dx
            if 0 <= nx < w and not collision[spawn_y][nx]:
                spawn_x = nx
                break

    return LocalMap(
        width=w, height=h,
        terrain=terrain, collision=collision,
        objects=objects, exits=exits,
        spawn=[spawn_x, spawn_y],
    )


def _compute_exit_positions(
    location: Location, w: int, h: int,
) -> dict[str, tuple[int, int]]:
    """Map location exits to border positions on the local map.

    Uses direction hints from coordinate differences when available,
    falls back to sequential placement on available borders.
    """
    positions: dict[str, tuple[int, int]] = {}
    used: set[tuple[int, int]] = set()

    # Direction-to-border mapping
    direction_borders = {
        "east": lambda w, h: (w - 1, h // 2),
        "west": lambda w, h: (0, h // 2),
        "north": lambda w, h: (w // 2, 0),
        "south": lambda w, h: (w // 2, h - 1),
        "northeast": lambda w, h: (w - 1, 1),
        "northwest": lambda w, h: (0, 1),
        "southeast": lambda w, h: (w - 1, h - 2),
        "southwest": lambda w, h: (0, h - 2),
    }

    # Reverse direction mapping for finding the approach direction
    reverse_dir = {
        "east": "west", "west": "east",
        "north": "south", "south": "north",
        "northeast": "southwest", "southwest": "northeast",
        "northwest": "southeast", "southeast": "northwest",
        "back": "east", "forward": "west",
        "in": "east", "out": "west",
        "inside": "east", "outside": "west",
        "up": "north", "down": "south",
        "upstairs": "north", "downstairs": "south",
    }

    # First pass: place exits with known directions
    for exit_name in location.exits:
        if exit_name in direction_borders:
            pos = direction_borders[exit_name](w, h)
            if pos not in used:
                positions[exit_name] = pos
                used.add(pos)
                continue

        # Try reverse direction
        rev = reverse_dir.get(exit_name, "")
        if rev in direction_borders:
            # Place on the opposite side
            pos = direction_borders[rev](w, h)
            if pos not in used:
                positions[exit_name] = pos
                used.add(pos)
                continue

    # Second pass: place remaining exits on available borders
    border_slots = [
        (w - 1, h // 2),       # east
        (0, h // 2),            # west
        (w // 2, 0),            # north
        (w // 2, h - 1),        # south
        (w - 1, 1),             # northeast
        (0, 1),                 # northwest
        (w - 1, h - 2),        # southeast
        (0, h - 2),             # southwest
        (w // 3, 0),            # north-left
        (2 * w // 3, 0),       # north-right
        (w // 3, h - 1),       # south-left
        (2 * w // 3, h - 1),   # south-right
    ]

    for exit_name in location.exits:
        if exit_name in positions:
            continue
        for slot in border_slots:
            if slot not in used:
                positions[exit_name] = slot
                used.add(slot)
                break

    return positions


def _guess_entry_name(exit_name: str) -> str:
    """Guess the entry name for a reverse transition.

    When the player walks from location A to B via exit 'east',
    the entry point in B should accept a return from 'west'.
    """
    reverse = {
        "east": "west", "west": "east",
        "north": "south", "south": "north",
        "northeast": "southwest", "southwest": "northeast",
        "northwest": "southeast", "southeast": "northwest",
        "back": "forward", "forward": "back",
        "in": "out", "out": "in",
        "inside": "outside", "outside": "inside",
        "up": "down", "down": "up",
        "upstairs": "downstairs", "downstairs": "upstairs",
    }
    return reverse.get(exit_name, "back")


# ---------------------------------------------------------------------------
# NPC & Interactable placement
# ---------------------------------------------------------------------------

def place_npcs_on_local_map(
    lm: LocalMap,
    npcs: list,
    *,
    occupied: set | None = None,
) -> None:
    """Place NPCs onto walkable tiles in the local map.

    Each NPC gets local_x / local_y set to a valid walkable tile that is
    not inside a wall, not on a blocking object, and not on an exit.
    Avoids overlapping with *occupied* (other NPCs/interactables already
    placed).  NPCs are non-blocking (the player can walk onto their tile).
    """
    if occupied is None:
        occupied = set()

    w, h = lm.width, lm.height
    exit_positions = {(ep.x, ep.y) for ep in lm.exits.values()}

    # Build set of blocking object tiles
    blocking_tiles: set[tuple[int, int]] = set()
    for obj in lm.objects:
        if obj.blocking:
            for dy in range(obj.height):
                for dx in range(obj.width):
                    blocking_tiles.add((obj.x + dx, obj.y + dy))

    for npc in npcs:
        if npc.local_x >= 0 and npc.local_y >= 0:
            # Already placed — validate and keep if still valid
            nx, ny = npc.local_x, npc.local_y
            if (0 <= nx < w and 0 <= ny < h
                    and not lm.collision[ny][nx]
                    and (nx, ny) not in blocking_tiles
                    and (nx, ny) not in exit_positions
                    and (nx, ny) not in occupied):
                occupied.add((nx, ny))
                continue

        placed = False
        for by in range(1, h - 1):
            for bx in range(1, w - 1):
                if (lm.collision[by][bx]
                        or (bx, by) in blocking_tiles
                        or (bx, by) in exit_positions
                        or (bx, by) in occupied):
                    continue
                npc.local_x = bx
                npc.local_y = by
                occupied.add((bx, by))
                placed = True
                break
            if placed:
                break

        if not placed:
            npc.local_x = -1
            npc.local_y = -1


def place_interactables_on_local_map(
    lm: LocalMap,
    interactables: list,
    *,
    occupied: set | None = None,
) -> None:
    """Place interactables onto walkable tiles in the local map.

    Same logic as NPC placement but for interactable objects.
    """
    if occupied is None:
        occupied = set()

    w, h = lm.width, lm.height
    exit_positions = {(ep.x, ep.y) for ep in lm.exits.values()}

    blocking_tiles: set[tuple[int, int]] = set()
    for obj in lm.objects:
        if obj.blocking:
            for dy in range(obj.height):
                for dx in range(obj.width):
                    blocking_tiles.add((obj.x + dx, obj.y + dy))

    for inter in interactables:
        if inter.local_x >= 0 and inter.local_y >= 0:
            nx, ny = inter.local_x, inter.local_y
            if (0 <= nx < w and 0 <= ny < h
                    and not lm.collision[ny][nx]
                    and (nx, ny) not in blocking_tiles
                    and (nx, ny) not in exit_positions
                    and (nx, ny) not in occupied):
                occupied.add((nx, ny))
                continue

        placed = False
        for by in range(1, h - 1):
            for bx in range(1, w - 1):
                if (lm.collision[by][bx]
                        or (bx, by) in blocking_tiles
                        or (bx, by) in exit_positions
                        or (bx, by) in occupied):
                    continue
                inter.local_x = bx
                inter.local_y = by
                occupied.add((bx, by))
                placed = True
                break
            if placed:
                break

        if not placed:
            inter.local_x = -1
            inter.local_y = -1


def _place_npcs_and_interactables(
    lm: LocalMap,
    location: 'Location',
    world_npcs: dict,
    world_interactables: dict,
) -> None:
    """Place all NPCs and interactables belonging to a location onto its map.

    Called after generate_local_map() for both hand-authored and
    AI-generated locations.
    """
    occupied: set[tuple[int, int]] = set()

    loc_npcs = [world_npcs[nid] for nid in location.npcs if nid in world_npcs]
    place_npcs_on_local_map(lm, loc_npcs, occupied=occupied)

    loc_inters = [world_interactables[iid]
                  for iid in location.interactables
                  if iid in world_interactables]
    place_interactables_on_local_map(lm, loc_inters, occupied=occupied)
