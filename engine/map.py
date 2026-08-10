"""Map rendering for the Infinite RPG.

Provides a width-aware compact map for the persistent sidebar
and a detailed full-screen map for the /map overlay.
"""

from typing import List, Tuple

from .state import GameState, World
from .terminal import (
    visible_width,
    strip_ansi,
    pad_to_width,
    truncate_to_width,
    colorize,
    FG,
)


# ---------------------------------------------------------------------------
# Shared data extraction
# ---------------------------------------------------------------------------

def get_map_bounds(world: World) -> Tuple[int, int, int, int]:
    if not world.locations:
        return (0, 0, 0, 0)
    xs = [loc.map_x for loc in world.locations.values()]
    ys = [loc.map_y for loc in world.locations.values()]
    return (min(xs), max(xs), min(ys), max(ys))


def get_connections(world: World) -> List[Tuple[str, str, str]]:
    connections = []
    seen = set()
    for loc in world.locations.values():
        for direction, target_id in loc.exits.items():
            pair = tuple(sorted((loc.id, target_id)))
            if pair not in seen:
                seen.add(pair)
                connections.append((loc.id, target_id, direction))
    return connections


def build_location_info(game: GameState) -> dict:
    world = game.world
    player = game.player
    visited = game.visited_locations

    info = {}
    for loc_id, loc in world.locations.items():
        npcs = []
        for npc_id in loc.npcs:
            npc = world.npcs.get(npc_id)
            if npc and npc.hp > 0:
                npcs.append(npc.name)

        items = list(loc.items)

        interactables = []
        for inter_id in loc.interactables:
            inter = world.interactables.get(inter_id)
            if inter:
                state_str = f" [{inter.state}]" if inter.state != "default" else ""
                interactables.append(f"{inter.name}{state_str}")

        info[loc_id] = {
            "loc": loc,
            "is_current": loc_id == player.location,
            "is_visited": loc_id in visited,
            "npcs": npcs,
            "items": items,
            "interactables": interactables,
        }

    return info


# ---------------------------------------------------------------------------
# Compact persistent map (for right sidebar)
# ---------------------------------------------------------------------------

def render_compact_map(game: GameState, width: int, max_height: int = 0) -> List[str]:
    """Render a compact map that fits within `width` visible columns.

    Uses a vertical node-graph layout:
    - Each location on its own row as "[name]"
    - Current: [@ name], Visited: [* name], Unknown: [  name]
    - Vertical connections shown with │
    - Horizontal connections shown with ──
    - Markers (N/I) inline after each node

    If max_height > 0, truncate output to fit within that many lines,
    keeping the title and current-location marker visible.
    """
    world = game.world
    if not world.locations:
        return [pad_to_width("  (no map data)", width)]

    loc_info = build_location_info(game)

    # Build lookup: (x,y) -> loc_id
    grid = {}
    for loc_id, loc in world.locations.items():
        grid[(loc.map_x, loc.map_y)] = loc_id

    min_x, max_x, min_y, max_y = get_map_bounds(world)

    # Calculate max name width for truncation
    # Node: "  [prefix name]" = 2 + 1 + 2 + name + 1 = name + 6
    # Markers: " NI" = 3 (worst case)
    # Connection: " ──" = 3
    # Worst case total: name + 6 + 3 + 3 = name + 12
    node_char_budget = max(4, width - 12)

    lines = []

    # Title
    lines.append(pad_to_width(" MAP", width))

    # Render each location as a node row
    # Process top-to-bottom (y descending)
    for y in range(max_y, min_y - 1, -1):
        # Check if any location exists on this row
        row_locs = []
        for x in range(min_x, max_x + 1):
            loc_id = grid.get((x, y))
            if loc_id:
                row_locs.append((x, loc_id))

        if not row_locs:
            continue

        # Check for vertical connections from row above
        for x, loc_id in row_locs:
            loc = world.locations.get(loc_id)
            if not loc:
                continue

            # Check if any location on row y+1 connects down to this one
            has_up = False
            for x2 in range(min_x, max_x + 1):
                above_id = grid.get((x2, y + 1))
                if above_id:
                    above_loc = world.locations.get(above_id)
                    if above_loc:
                        for direction, target_id in above_loc.exits.items():
                            if target_id == loc_id:
                                has_up = True
                                break
                if has_up:
                    break

            if has_up:
                # Indent to roughly align under the parent node
                indent = " " * min(5, width // 4)
                lines.append(pad_to_width(indent + "\u2502", width))

        # Render each location node on this row
        for x, loc_id in row_locs:
            info = loc_info[loc_id]
            loc = info["loc"]

            # Build node name
            name = loc.name
            if visible_width(name) > node_char_budget:
                name = truncate_to_width(name, node_char_budget, "..")

            # Prefix based on status
            if info["is_current"]:
                prefix = "@ "
                name_color = FG.BRIGHT_GREEN
            elif info["is_visited"]:
                prefix = "* "
                name_color = FG.DIM
            else:
                prefix = "  "
                name_color = None

            # Markers
            markers = ""
            if info["npcs"]:
                markers += "N"
            if info["items"] or info["interactables"]:
                markers += "I"

            # Build the node line
            node = f"[{prefix}{name}]"
            if markers:
                node += f" {colorize(markers, FG.BRIGHT_YELLOW)}"

            # Check for horizontal connections to the right
            right_conn = False
            for direction, target_id in loc.exits.items():
                target = world.locations.get(target_id)
                if target and target.map_x == x + 1 and target.map_y == y:
                    right_conn = True
                    break

            if right_conn:
                node += " \u2500\u2500"

            lines.append(pad_to_width(truncate_to_width("  " + node, width), width))

    # Legend — truncate to fit width
    legend = " @You *Visited N=NPC I=Item"
    if visible_width(legend) > width - 2:
        legend = " @You *Vis N=NP I=It"
    lines.append("")
    lines.append(pad_to_width(legend, width))

    # Height truncation: keep title + current location if possible
    if max_height > 0 and len(lines) > max_height:
        truncated = lines[:1]  # always keep MAP title
        # Find the current location line (starts with "  [@")
        current_line = None
        for l in lines[1:]:
            stripped = strip_ansi(l).lstrip()
            if stripped.startswith("[@"):
                current_line = l
                break
        if current_line and max_height >= 3:
            truncated.append(pad_to_width("", width))
            truncated.append(current_line)
            if max_height >= 4:
                truncated.append(pad_to_width("  (...)", width))
        elif max_height >= 2:
            truncated.append(pad_to_width("  (map hidden)", width))
        lines = truncated[:max_height]

    return lines


# ---------------------------------------------------------------------------
# Detailed full-screen map (for /map overlay)
# ---------------------------------------------------------------------------

def render_map(game: GameState) -> str:
    """Render a detailed ASCII map for the /map overlay."""
    world = game.world
    player = game.player
    visited = game.visited_locations

    if not world.locations:
        return "No locations discovered."

    min_x, max_x, min_y, max_y = get_map_bounds(world)
    connections = get_connections(world)
    loc_info = build_location_info(game)

    lines = []
    lines.append("                         WORLD MAP")
    lines.append("")

    w = world.weather
    lines.append(
        f"                         Weather: {w.condition.title()} | {w.temperature}\u00b0C"
    )
    lines.append("")

    for y in range(max_y, min_y - 1, -1):
        row_locations = []
        for x in range(min_x, max_x + 1):
            loc_at_pos = None
            for loc_id, loc in world.locations.items():
                if loc.map_x == x and loc.map_y == y:
                    loc_at_pos = loc_id
                    break

            if loc_at_pos:
                info = loc_info[loc_at_pos]
                loc = info["loc"]

                if info["is_current"]:
                    prefix = "@ "
                elif info["is_visited"]:
                    prefix = "* "
                else:
                    prefix = "  "

                name = loc.name
                if len(name) > 15:
                    name = name[:12] + "..."

                label = f"{prefix}{name}"
                row_locations.append((x, label, loc_at_pos))
            else:
                row_locations.append((x, "                ", None))

        name_line = "                         "
        for i, (x, label, loc_id) in enumerate(row_locations):
            name_line += f"[{label}]"
            if i < len(row_locations) - 1:
                name_line += "  "
        lines.append(name_line)

        detail_line = "                         "
        for i, (x, label, loc_id) in enumerate(row_locations):
            if loc_id:
                info = loc_info[loc_id]
                markers = ""
                if info["npcs"]:
                    markers += "N"
                if info["items"] or info["interactables"]:
                    markers += "I"
                if not markers:
                    markers = " "
                detail_line += f"    {markers}     "
            else:
                detail_line += "           "
            if i < len(row_locations) - 1:
                detail_line += "  "
        lines.append(detail_line)

        if y > min_y:
            conn_line = "                         "
            for i, (x, label, loc_id) in enumerate(row_locations):
                has_conn = False
                for c_loc, c_target, _ in connections:
                    if c_loc == loc_id or c_target == loc_id:
                        other_id = c_target if c_loc == loc_id else c_loc
                        target_loc = world.locations.get(other_id)
                        if target_loc and target_loc.map_y == y - 1:
                            has_conn = True
                            break
                if has_conn:
                    conn_line += "    |     "
                else:
                    conn_line += "          "
                if i < len(row_locations) - 1:
                    conn_line += "  "
            lines.append(conn_line)

    lines.append("")
    lines.append("                         CONNECTIONS")
    for loc_id, target_id, direction in connections:
        loc = world.locations.get(loc_id)
        target = world.locations.get(target_id)
        if loc and target:
            lines.append(
                f"                         {loc.name} <-> {target.name}"
            )

    lines.append("")
    lines.append("                         LEGEND")
    lines.append("                         @ You | * Visited | N NPC | I Item")
    lines.append("")

    return "\n".join(lines)


def get_location_details(game: GameState, location_id: str) -> str:
    """Get detailed information about a specific location."""
    world = game.world
    loc = world.locations.get(location_id)

    if not loc:
        return f"Location '{location_id}' not found."

    lines = []
    lines.append(f"=== {loc.name} ===")
    lines.append(loc.description)
    lines.append("")

    npcs_at_location = []
    for npc_id in loc.npcs:
        npc = world.npcs.get(npc_id)
        if npc and npc.hp > 0:
            npcs_at_location.append(npc)

    if npcs_at_location:
        lines.append("NPCs:")
        for npc in npcs_at_location:
            lines.append(f"  - {npc.name}")
        lines.append("")

    if loc.items:
        lines.append("Items:")
        for item in loc.items:
            lines.append(f"  - {item}")
        lines.append("")

    interactables_at_location = []
    for inter_id in loc.interactables:
        inter = world.interactables.get(inter_id)
        if inter:
            interactables_at_location.append(inter)

    if interactables_at_location:
        lines.append("Interactables:")
        for inter in interactables_at_location:
            state_str = f" [{inter.state}]" if inter.state != "default" else ""
            lines.append(f"  - {inter.name}{state_str}")
        lines.append("")

    if loc.exits:
        lines.append("Exits:")
        for direction, target_id in loc.exits.items():
            target = world.locations.get(target_id)
            if target:
                lines.append(f"  - {direction} -> {target.name}")
            else:
                lines.append(f"  - {direction} -> Unknown")
        lines.append("")

    return "\n".join(lines)
