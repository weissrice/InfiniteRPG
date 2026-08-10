"""AI World Generation — creates persistent locations, NPCs, items, and connections."""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from typing import Any

from .ai import AIClient
from .state import GameState, Interactable, Location, NPC


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class GenerationResult:
    """Result of a world generation attempt."""
    success: bool
    location: Location | None = None
    npcs: list[NPC] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    interactables: list[Interactable] = field(default_factory=list)
    narration: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Direction helpers
# ---------------------------------------------------------------------------

_DIRECTION_VECTORS: dict[str, tuple[int, int]] = {
    "east": (1, 0),
    "west": (-1, 0),
    "south": (0, 1),
    "north": (0, -1),
    "northeast": (1, -1),
    "northwest": (-1, -1),
    "southeast": (1, 1),
    "southwest": (-1, 1),
}

_REVERSE_DIRECTIONS: dict[str, str] = {
    "east": "west",
    "west": "east",
    "north": "south",
    "south": "north",
    "northeast": "southwest",
    "southwest": "northeast",
    "northwest": "southeast",
    "southeast": "northwest",
    "back": "forward",
    "forward": "back",
    "in": "out",
    "out": "in",
    "inside": "outside",
    "outside": "inside",
    "up": "down",
    "down": "up",
    "upstairs": "downstairs",
    "downstairs": "upstairs",
}

# Visual types that represent interior spaces (share parent coordinates)
_INTERIOR_TYPES: set[str] = {
    "interior", "house", "building", "dungeon", "cave",
    "room", "hall", "tower", "basement", "attic",
    "tunnel", "corridor", "chamber", "crypt",
}


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_GENERATION_SYSTEM_PROMPT = """\
You generate world content for an AI-driven procedural RPG.

Return ONLY valid JSON. No markdown. No explanation.

The JSON must contain a "location" object and may contain "npcs", \
"items", "interactables", and "connections" arrays.

Rules:
- Generate exactly ONE location with supporting content.
- The content must fit the current world, weather, and surroundings.
- Do NOT create content that already exists in the world.
- NPCs should have meaningful personalities, knowledge, and goals.
- Items should be appropriate to the location.
- Interactable objects should have clear descriptions and states.
- Connections describe how this location links to others.
- Keep descriptions immersive but concise.
- visual_type describes the terrain or structure: \
forest, village, city, cave, ruins, mountain, water, road, \
dungeon, temple, tower, farm, camp, ship, desert, island, \
interior, house, building, or any other appropriate type.
- is_interior=true means the location is inside a structure \
(same coordinates as the parent location).
"""


def _build_generation_prompt(
    game: GameState,
    reference: Location,
    direction: str,
    context_hint: str,
) -> str:
    """Build the user prompt for world generation."""

    nearby = []
    for loc in game.world.locations.values():
        exits_str = ", ".join(loc.exits.keys()) if loc.exits else "none"
        nearby.append(
            f"- {loc.id} ({loc.name}) at ({loc.map_x}, {loc.map_y}) "
            f"exits: {exits_str}"
        )
    nearby_text = "\n".join(nearby) if nearby else "(none)"

    npc_list = []
    for npc in game.world.npcs.values():
        if npc.hp > 0:
            npc_list.append(f"- {npc.name} ({npc.id}) at {npc.location}")
    npc_text = "\n".join(npc_list) if npc_list else "(none)"

    hint_line = ""
    if context_hint:
        hint_line = f"\nHINT: {context_hint}"

    return f"""\
CURRENT WORLD:
World: {game.world.name}
Genre: {game.world.genre}
Day: {game.world.day}, Time: {game.world.time}
Weather: {game.world.weather.condition.title()} {game.world.weather.temperature}°C

CURRENT LOCATION:
ID: {reference.id}
Name: {reference.name}
Description: {reference.description}
Coordinates: ({reference.map_x}, {reference.map_y})
Exits: {', '.join(reference.exits.keys()) if reference.exits else 'none'}
Items: {', '.join(reference.items) if reference.items else 'none'}
NPCs: {', '.join(reference.npcs) if reference.npcs else 'none'}

ALL KNOWN LOCATIONS:
{nearby_text}

ALL KNOWN NPCs:
{npc_text}

PLAYER INVENTORY:
{', '.join(game.player.inventory) if game.player.inventory else 'empty'}
Player Money: {game.player.money}g

DIRECTION: {direction}{hint_line}

Generate new world content that exists {direction} of the current location.

Return the JSON immediately.
"""


# ---------------------------------------------------------------------------
# Parsing & validation
# ---------------------------------------------------------------------------

def _parse_generation_response(response: str) -> dict[str, Any] | None:
    """Parse the AI's JSON response."""
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    loc = data.get("location")
    if not isinstance(loc, dict):
        return None

    required = ["name", "description"]
    for field_name in required:
        if not isinstance(loc.get(field_name), str) or not loc[field_name].strip():
            return None

    return data


def _validate_generation(data: dict, game: GameState) -> bool:
    """Validate that generated data is safe and well-formed."""
    loc = data.get("location", {})
    if not loc.get("name") or not loc.get("description"):
        return False

    if not isinstance(loc.get("visual_type", ""), str):
        return False

    for npc_data in data.get("npcs", []):
        if not isinstance(npc_data, dict):
            return False
        if not npc_data.get("name") or not isinstance(npc_data["name"], str):
            return False

    for item in data.get("items", []):
        if not isinstance(item, str):
            return False

    for obj in data.get("interactables", []):
        if not isinstance(obj, dict):
            return False
        if not obj.get("name") or not obj.get("description"):
            return False

    for conn in data.get("connections", []):
        if not isinstance(conn, dict):
            return False

    return True


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def _make_safe_id(name: str) -> str:
    """Convert a name to a snake_case ID."""
    value = name.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "unnamed_location"


def _assign_id(game: GameState, name: str) -> str:
    """Generate a stable unique ID, avoiding collisions."""
    base = _make_safe_id(name)
    if base not in game.world.locations:
        return base

    suffix = format(random.randint(0, 0xFFFF), "04x")
    candidate = f"{base}_{suffix}"
    attempts = 0
    while candidate in game.world.locations and attempts < 10:
        suffix = format(random.randint(0, 0xFFFF), "04x")
        candidate = f"{base}_{suffix}"
        attempts += 1

    return candidate


# ---------------------------------------------------------------------------
# Coordinate computation
# ---------------------------------------------------------------------------

def _compute_coordinates(
    game: GameState,
    reference: Location,
    direction: str,
    is_interior: bool,
) -> tuple[int, int]:
    """Compute map_x, map_y for a new location."""
    if is_interior:
        return reference.map_x, reference.map_y

    dx, dy = _DIRECTION_VECTORS.get(direction.lower(), (1, 0))
    target_x = reference.map_x + dx
    target_y = reference.map_y + dy

    return _find_free_cell(game, target_x, target_y, (dx, dy))


def _find_free_cell(
    game: GameState,
    x: int,
    y: int,
    direction: tuple[int, int],
) -> tuple[int, int]:
    """Find the nearest unoccupied grid cell starting from (x, y)."""
    occupied: set[tuple[int, int]] = set()
    for loc in game.world.locations.values():
        occupied.add((loc.map_x, loc.map_y))

    if (x, y) not in occupied:
        return x, y

    for offset in range(1, 30):
        candidates = []
        for dx_off in range(-offset, offset + 1):
            for dy_off in range(-offset, offset + 1):
                if abs(dx_off) != offset and abs(dy_off) != offset:
                    continue
                cx = x + dx_off
                cy = y + dy_off
                if (cx, cy) not in occupied:
                    candidates.append((cx, cy))
        if candidates:
            candidates.sort(key=lambda c: (
                abs(c[0] - x) + abs(c[1] - y),
                random.random(),
            ))
            return candidates[0]

    return x, y


# ---------------------------------------------------------------------------
# Connection creation
# ---------------------------------------------------------------------------

def _guess_direction_label(from_loc: Location, to_loc: Location) -> str:
    """Infer a direction label from the coordinate difference."""
    dx = to_loc.map_x - from_loc.map_x
    dy = to_loc.map_y - from_loc.map_y

    if dx > 0 and dy == 0:
        return "east"
    if dx < 0 and dy == 0:
        return "west"
    if dx == 0 and dy > 0:
        return "south"
    if dx == 0 and dy < 0:
        return "north"
    if dx > 0 and dy < 0:
        return "northeast"
    if dx < 0 and dy < 0:
        return "northwest"
    if dx > 0 and dy > 0:
        return "southeast"
    if dx < 0 and dy > 0:
        return "southwest"
    return "path"


def _reverse_direction(label: str) -> str:
    """Get the reverse of a direction label."""
    return _REVERSE_DIRECTIONS.get(label, "back")


def _create_connections(
    game: GameState,
    new_location: Location,
    reference: Location,
    connections: list[dict],
) -> None:
    """Create connections between locations."""
    direction_label = _guess_direction_label(reference, new_location)
    reference.exits[direction_label] = new_location.id

    is_one_way = any(c.get("one_way", False) for c in connections)

    if not is_one_way:
        reverse = _reverse_direction(direction_label)
        new_location.exits[reverse] = reference.id

    for conn in connections:
        target_id = conn.get("to", "")
        if target_id and target_id in game.world.locations:
            label = conn.get("label", "path")
            one_way = conn.get("one_way", False)

            if label not in new_location.exits:
                new_location.exits[label] = target_id

            if not one_way:
                target = game.world.locations[target_id]
                reverse = _reverse_direction(label)
                if reverse not in target.exits:
                    target.exits[reverse] = new_location.id


# ---------------------------------------------------------------------------
# Entity registration
# ---------------------------------------------------------------------------

def _register_npcs(
    game: GameState,
    location_id: str,
    npcs_data: list[dict],
) -> list[NPC]:
    """Register generated NPCs and return them."""
    registered = []
    for npc_data in npcs_data:
        name = npc_data.get("name", "").strip()
        if not name:
            continue

        npc_id = _make_safe_id(name)
        if npc_id in game.world.npcs:
            suffix = format(random.randint(0, 0xFFFF), "04x")
            npc_id = f"{npc_id}_{suffix}"

        npc = NPC(
            id=npc_id,
            name=name,
            location=location_id,
            description=npc_data.get("description", ""),
            disposition=npc_data.get("disposition", 0),
            personality=npc_data.get("personality", []),
            knowledge=npc_data.get("knowledge", []),
            beliefs=npc_data.get("beliefs", []),
            goals=npc_data.get("goals", []),
            relationships=npc_data.get("relationships", {}),
            routine=npc_data.get("routine", []),
            schedule=npc_data.get("schedule", {}),
            current_activity=npc_data.get("current_activity", ""),
            inventory=npc_data.get("inventory", []),
            money=npc_data.get("money", 0),
            hp=npc_data.get("hp", 100),
            max_hp=npc_data.get("max_hp", 100),
        )
        game.world.npcs[npc_id] = npc
        registered.append(npc)

    return registered


def _register_items(
    location: Location,
    items_data: list[str | dict],
) -> list[str]:
    """Add items to a location."""
    items = []
    for item in items_data:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = item.get("name", "").strip()
        else:
            continue
        if name and name not in location.items:
            location.items.append(name)
            items.append(name)
    return items


def _register_interactables(
    game: GameState,
    location_id: str,
    interactables_data: list[dict],
) -> list[Interactable]:
    """Register generated interactable objects."""
    registered = []
    for obj_data in interactables_data:
        name = obj_data.get("name", "").strip()
        description = obj_data.get("description", "").strip()
        if not name or not description:
            continue

        obj_id = _make_safe_id(name)
        if obj_id in game.world.interactables:
            suffix = format(random.randint(0, 0xFFFF), "04x")
            obj_id = f"{obj_id}_{suffix}"

        obj = Interactable(
            id=obj_id,
            name=name,
            description=description,
            location=location_id,
            state=obj_data.get("state", "default"),
            unlock_items=obj_data.get("unlock_items", []),
        )
        game.world.interactables[obj_id] = obj
        registered.append(obj)

    return registered


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

def generate_world_content(
    game: GameState,
    ai: AIClient,
    reference_location_id: str,
    direction: str,
    context_hint: str = "",
) -> GenerationResult:
    """Generate new world content (location, NPCs, items, connections).

    Args:
        game: Current game state.
        ai: AI client for generation.
        reference_location_id: ID of the location this content is relative to.
        direction: Direction string ("east", "north", "inside", etc.).
        context_hint: Optional hint about what should be there.

    Returns:
        GenerationResult with generated entities and status.
    """
    reference = game.world.locations.get(reference_location_id)
    if reference is None:
        return GenerationResult(
            success=False,
            error=f"Reference location '{reference_location_id}' not found.",
        )

    prompt = _build_generation_prompt(game, reference, direction, context_hint)

    try:
        response = ai.ask(
            prompt=prompt,
            system=_GENERATION_SYSTEM_PROMPT,
            max_tokens=4096,
            temperature=0.8,
            json_mode=True,
        )
    except Exception as e:
        return GenerationResult(
            success=False,
            error=f"AI generation failed: {e}",
        )

    data = _parse_generation_response(response)
    if data is None:
        return GenerationResult(
            success=False,
            error="Failed to parse AI generation response.",
        )

    if not _validate_generation(data, game):
        return GenerationResult(
            success=False,
            error="AI generation failed validation.",
        )

    loc_data = data["location"]
    name = loc_data["name"].strip()
    visual_type = loc_data.get("visual_type", "area").strip()
    is_interior = loc_data.get("is_interior", False) or visual_type.lower() in _INTERIOR_TYPES

    location_id = _assign_id(game, name)

    map_x, map_y = _compute_coordinates(game, reference, direction, is_interior)

    new_location = Location(
        id=location_id,
        name=name,
        description=loc_data["description"].strip(),
        exits={},
        visual_type=visual_type,
        symbol=loc_data.get("symbol", "?")[:2] if isinstance(loc_data.get("symbol"), str) else "?",
        map_x=map_x,
        map_y=map_y,
    )

    game.world.locations[location_id] = new_location

    connections = data.get("connections", [])
    _create_connections(game, new_location, reference, connections)

    items = _register_items(new_location, data.get("items", []))

    npcs = _register_npcs(game, location_id, data.get("npcs", []))
    for npc in npcs:
        if location_id not in new_location.npcs:
            new_location.npcs.append(npc.id)

    interactables = _register_interactables(game, location_id, data.get("interactables", []))
    for obj in interactables:
        if location_id not in new_location.interactables:
            new_location.interactables.append(obj.id)

    game.visited_locations.add(location_id)

    return GenerationResult(
        success=True,
        location=new_location,
        npcs=npcs,
        items=items,
        interactables=interactables,
    )
