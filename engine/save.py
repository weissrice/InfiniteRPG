import json
from dataclasses import asdict
from pathlib import Path

from .state import GameState, Player, World, Location, NPC, Quest, QuestObjective, Weather, WorldEvent


SAVE_FILE = Path("rpg_save.json")
SAVE_VERSION = 5


def _load_weather(raw) -> Weather:
    """Convert raw weather data to a Weather instance.

    Handles both legacy string values (e.g. "Rain") and the new dict
    format produced by dataclasses.asdict().
    """
    if isinstance(raw, str):
        return Weather(condition=raw.lower())
    if isinstance(raw, dict):
        return Weather(
            condition=raw.get("condition", "clear"),
            temperature=raw.get("temperature", 25),
        )
    return Weather()


def save_game(game: GameState, path: Path = SAVE_FILE):
    """Save the complete game state to JSON."""

    data = asdict(game)
    data["version"] = SAVE_VERSION

    # Convert visited_locations set to list for JSON serialization
    if "visited_locations" in data:
        data["visited_locations"] = list(data["visited_locations"])

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
        weather=_load_weather(world_data.get("weather")),
        seed=world_data.get("seed", 0),
        locations=locations,
        npcs=npcs,
    )

    # Reconstruct quests (backward-compatible: old saves have none)
    quests = {}
    quests_data = data.get("quests", {})
    for quest_id, quest_data in quests_data.items():
        objectives = []
        for obj_data in quest_data.get("objectives", []):
            objectives.append(QuestObjective(
                id=obj_data["id"],
                type=obj_data["type"],
                target=obj_data["target"],
                description=obj_data["description"],
                required=obj_data.get("required", 1),
                current=obj_data.get("current", 0),
            ))
        quests[quest_id] = Quest(
            id=quest_data["id"],
            title=quest_data["title"],
            description=quest_data["description"],
            giver=quest_data["giver"],
            state=quest_data.get("state", "offered"),
            objectives=objectives,
            rewards=quest_data.get("rewards", {}),
            offered_at=quest_data.get("offered_at", ""),
            offered_time=quest_data.get("offered_time", ""),
        )

    # Reconstruct world events (backward-compatible: old saves have none)
    events = []
    events_data = data.get("events", [])
    for ev_data in events_data:
        events.append(WorldEvent(
            id=ev_data.get("id", ""),
            type=ev_data.get("type", ""),
            title=ev_data.get("title", ""),
            description=ev_data.get("description", ""),
            location=ev_data.get("location", ""),
            actors=ev_data.get("actors", []),
            day=ev_data.get("day", 0),
            time=ev_data.get("time", "00:00"),
            resolved=ev_data.get("resolved", True),
        ))

    last_event_period = data.get("last_event_period", -1)

    return GameState(
        player=player,
        world=world,
        quests=quests,
        visited_locations=set(data.get("visited_locations", [])),
        events=events,
        last_event_period=last_event_period,
    )