import json
from dataclasses import asdict
from pathlib import Path

from .state import GameState, Player, World, Location, NPC


SAVE_FILE = Path("rpg_save.json")
SAVE_VERSION = 1


def save_game(game: GameState, path: Path = SAVE_FILE):
    """Save the complete game state to JSON."""

    data = asdict(game)
    data["version"] = SAVE_VERSION

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def load_game(path: Path = SAVE_FILE) -> GameState:
    """Load a complete game state from JSON.

    Backward-compatible: saves without a version field are treated as
    version 1 (the original format).
    """

    if not path.exists():
        raise FileNotFoundError(
            f"No save file found at {path.resolve()}"
        )

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    # Version is optional for backward compatibility with pre-versioned
    # save files.  Absent version is treated as 1.
    _version = data.get("version", 1)

    player_data = data["player"]
    world_data = data["world"]

    player = Player(**player_data)

    locations = {
        location_id: Location(
            **location_data
        )
        for location_id, location_data in world_data["locations"].items()
    }

    npcs = {
        npc_id: NPC(
            **npc_data
        )
        for npc_id, npc_data in world_data["npcs"].items()
    }

    world = World(
        name=world_data["name"],
        genre=world_data["genre"],
        time=world_data["time"],
        day=world_data["day"],
        weather=world_data["weather"],
        locations=locations,
        npcs=npcs,
    )

    return GameState(
        player=player,
        world=world,
    )