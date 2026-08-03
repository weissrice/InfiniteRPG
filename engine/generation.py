import json
import re
from typing import Any

from .ai import AIClient
from .state import GameState, Location
from .world import add_generated_location


GENERATION_PROMPT = """
You generate ONE new location for an AI-driven procedural RPG.

Return ONLY valid JSON.
Do not use Markdown.
Do not explain your answer.

Return exactly:

{
  "id": "unique_location_id",
  "name": "Location Name",
  "description": "A detailed description of the location.",
  "visual_type": "forest",
  "symbol": "🌲",
  "items": [],
  "npcs": []
}

Rules:

- Generate exactly ONE location.
- The location must fit the current world and surroundings.
- Do not create exits.
- Do not create connections to other locations.
- Python will handle all map connections.
- Do not reuse an existing location ID.
- Keep the location appropriate for the world's genre.
- Do not create impossible or contradictory geography.
- visual_type should be a short category such as:
  forest, interior, house, cave, village, road, ruins, mountain, water, dungeon
- symbol should be ONE simple visual symbol.
- Items and NPCs should be empty unless they make sense.
"""


def _make_safe_id(value: str) -> str:
    """Convert an AI-generated name into a safe location ID."""

    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")

    return value or "unnamed_location"


def _parse_generation(response: str) -> dict[str, Any] | None:
    """Parse and validate the AI generation response."""

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    required = [
        "name",
        "description",
        "visual_type",
        "symbol",
    ]

    for field in required:
        if not isinstance(data.get(field), str):
            return None

    if not isinstance(data.get("items", []), list):
        return None

    if not isinstance(data.get("npcs", []), list):
        return None

    return data


def generate_location(
    game: GameState,
    ai: AIClient,
    direction: str,
) -> Location | None:
    """Generate a new location in the requested direction."""

    current = game.current_location()

    if current is None:
        return None

    existing_locations = []

    for location in game.world.locations.values():
        existing_locations.append(
            f"- {location.id}: {location.name}"
        )

    existing_text = "\n".join(existing_locations)

    prompt = f"""
CURRENT WORLD:

World name: {game.world.name}
Genre: {game.world.genre}
Weather: {game.world.weather.condition}
Day: {game.world.day}
Time: {game.world.time}

CURRENT LOCATION:

ID: {current.id}
Name: {current.name}
Description: {current.description}

PLAYER MOVEMENT:

The player wants to travel {direction}.

EXISTING LOCATIONS:

{existing_text}

Generate the single new location that lies {direction} of
the current location.

Do not generate exits or connections.
Python will create the map connection automatically.

Return the required JSON immediately.
"""

    response = ai.ask(
        prompt=prompt,
        system=GENERATION_PROMPT,
        max_tokens=4096,
        temperature=0.8,
        json_mode=True,
    )

    data = _parse_generation(response)

    if data is None:
        return None

    name = data["name"].strip()

    location_id = _make_safe_id(
        data.get("id", name)
    )

    if location_id in game.world.locations:
        location_id = _make_safe_id(name)

    if location_id in game.world.locations:
        return None

    location = Location(
        id=location_id,
        name=name,
        description=data["description"].strip(),
        exits={},
        items=[
            str(item)
            for item in data.get("items", [])
        ],
        npcs=[
            str(npc)
            for npc in data.get("npcs", [])
        ],
        symbol=data["symbol"].strip()[:2],
        visual_type=data["visual_type"].strip(),
    )

    if not add_generated_location(game, location):
        return None

    return location
