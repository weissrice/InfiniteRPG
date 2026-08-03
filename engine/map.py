from .state import GameState, Location


def render_map(game: GameState) -> str:
    """Render an ASCII map of the world.

    Returns a string representation of the map showing:
    - All locations with their positions
    - Connections between locations
    - Player's current position (@)
    - Visited locations (*)
    - NPCs at each location
    - Items/interactables at each location
    """

    world = game.world
    player = game.player
    visited = game.visited_locations

    if not world.locations:
        return "No locations discovered."

    # Find bounds
    min_x = min(loc.map_x for loc in world.locations.values())
    max_x = max(loc.map_x for loc in world.locations.values())
    min_y = min(loc.map_y for loc in world.locations.values())
    max_y = max(loc.map_y for loc in world.locations.values())

    # Build connection lines
    connections = []
    for loc in world.locations.values():
        for direction, target_id in loc.exits.items():
            target = world.locations.get(target_id)
            if target:
                # Avoid duplicate connections
                if (loc.id, target_id) not in [
                    (c[0], c[1]) for c in connections
                ] and (target_id, loc.id) not in [
                    (c[0], c[1]) for c in connections
                ]:
                    connections.append((loc.id, target_id, direction))

    # Build the map grid
    # Each location takes 3 lines: name, marker, details
    # Connections are shown between locations

    lines = []
    lines.append("                         WORLD MAP")
    lines.append("")

    # Build location info
    location_info = {}
    for loc_id, loc in world.locations.items():
        is_current = (loc_id == player.location)
        is_visited = (loc_id in visited)

        # Get NPCs at this location
        npcs_at_location = []
        for npc_id in loc.npcs:
            npc = world.npcs.get(npc_id)
            if npc and npc.hp > 0:
                npcs_at_location.append(npc.name)

        # Get items at this location
        items_at_location = list(loc.items)

        # Get interactables at this location
        interactables_at_location = []
        for inter_id in loc.interactables:
            inter = world.interactables.get(inter_id)
            if inter:
                state_str = f" [{inter.state}]" if inter.state != "default" else ""
                interactables_at_location.append(f"{inter.name}{state_str}")

        location_info[loc_id] = {
            "loc": loc,
            "is_current": is_current,
            "is_visited": is_visited,
            "npcs": npcs_at_location,
            "items": items_at_location,
            "interactables": interactables_at_location,
        }

    # Render map row by row
    for y in range(max_y, min_y - 1, -1):
        # Location line
        row_locations = []
        for x in range(min_x, max_x + 1):
            loc_at_pos = None
            for loc_id, loc in world.locations.items():
                if loc.map_x == x and loc.map_y == y:
                    loc_at_pos = loc_id
                    break

            if loc_at_pos:
                info = location_info[loc_at_pos]
                loc = info["loc"]

                # Build location label
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

        # Print location names
        name_line = "                         "
        for i, (x, label, loc_id) in enumerate(row_locations):
            name_line += f"[{label}]"
            if i < len(row_locations) - 1:
                name_line += "  "
        lines.append(name_line)

        # Print markers and details
        detail_line = "                         "
        for i, (x, label, loc_id) in enumerate(row_locations):
            if loc_id:
                info = location_info[loc_id]
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

        # Print connections (vertical)
        if y > min_y:
            conn_line = "                         "
            for i, (x, label, loc_id) in enumerate(row_locations):
                # Check if there's a vertical connection
                has_conn = False
                for conn in connections:
                    if conn[0] == loc_id or conn[1] == loc_id:
                        target_loc = world.locations.get(
                            conn[1] if conn[0] == loc_id else conn[0]
                        )
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

    # Print horizontal connections
    lines.append("")
    lines.append("                         CONNECTIONS")
    for loc_id, target_id, direction in connections:
        loc = world.locations.get(loc_id)
        target = world.locations.get(target_id)
        if loc and target:
            lines.append(
                f"                         {loc.name} <-> {target.name}"
            )

    # Print legend
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

    # NPCs
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

    # Items
    if loc.items:
        lines.append("Items:")
        for item in loc.items:
            lines.append(f"  - {item}")
        lines.append("")

    # Interactables
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

    # Exits
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
