from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class Weather:
    """Persistent weather state. Deterministic from (seed, time)."""
    condition: str = "clear"
    temperature: int = 25


@dataclass
class Player:
    name: str = "Traveler"
    hp: int = 100
    max_hp: int = 100
    location: str = "old_wooden_house"
    inventory: List[str] = field(
        default_factory=lambda: ["Rusty Key", "Torn Note"]
    )

    # Progression
    xp: int = 0
    level: int = 1
    stat_points: int = 0
    strength: int = 10
    vitality: int = 10
    agility: int = 10
    intelligence: int = 10

    # Trading
    money: int = 0


@dataclass
class QuestObjective:
    id: str
    type: str  # "kill", "find", "talk", "visit"
    target: str
    description: str
    required: int = 1
    current: int = 0

    @property
    def completed(self) -> bool:
        return self.current >= self.required


@dataclass
class Quest:
    id: str
    title: str
    description: str
    giver: str  # NPC id
    state: str = "offered"  # offered, active, completed, failed, abandoned
    objectives: List[QuestObjective] = field(default_factory=list)
    rewards: Dict = field(default_factory=dict)
    offered_at: str = ""
    offered_time: str = ""


@dataclass
class Recipe:
    id: str
    name: str
    ingredients: Dict[str, int]
    output: str
    output_quantity: int = 1


@dataclass
class NPC:
    id: str
    name: str
    location: str
    description: str = ""
    disposition: int = 0
    personality: List[str] = field(default_factory=list)
    memory: List[str] = field(default_factory=list)
    knowledge: List[str] = field(default_factory=list)
    beliefs: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    relationships: Dict[str, int] = field(default_factory=dict)
    routine: List[str] = field(default_factory=list)
    schedule: Dict[str, str] = field(default_factory=dict)
    current_activity: str = ""
    activity_by_time: Dict[str, str] = field(default_factory=dict)
    current_activity_object: str = ""
    activity_objects_by_time: Dict[str, str] = field(default_factory=dict)
    hp: int = 100
    max_hp: int = 100

    # Trading
    inventory: List[str] = field(default_factory=list)
    money: int = 0


@dataclass
class Interactable:
    id: str
    name: str
    description: str
    location: str
    state: str = "default"
    discovered: bool = False
    used: bool = False
    memory: List[str] = field(default_factory=list)
    unlock_items: List[str] = field(default_factory=list)


@dataclass
class Location:
    id: str
    name: str
    description: str
    exits: Dict[str, str] = field(default_factory=dict)
    npcs: List[str] = field(default_factory=list)
    items: List[str] = field(default_factory=list)
    interactables: List[str] = field(default_factory=list)

    # Visual information used by the dynamic renderer.
    symbol: str = "?"
    visual_type: str = "area"

    # Map coordinates for ASCII map rendering
    map_x: int = 0
    map_y: int = 0


@dataclass
class World:
    name: str = "Unnamed World"
    genre: str = "Fantasy"
    time: str = "12:00"
    day: int = 1
    weather: Weather = field(default_factory=Weather)
    seed: int = 0
    locations: Dict[str, Location] = field(default_factory=dict)
    npcs: Dict[str, NPC] = field(default_factory=dict)
    interactables: Dict[str, Interactable] = field(
        default_factory=dict
    )


@dataclass
class GameState:
    player: Player = field(default_factory=Player)
    world: World = field(default_factory=World)

    # Most recent AI-generated narration.
    last_narration: str = ""

    # Active/offered/completed/failed/abandoned quests.
    quests: Dict[str, Quest] = field(default_factory=dict)

    # Locations the player has visited
    visited_locations: Set[str] = field(default_factory=set)

    def current_location(self) -> Location | None:
        """Return the location where the player currently is."""
        return self.world.locations.get(self.player.location)

    def current_interactables(self) -> List[Interactable]:
        """Return interactable objects at the player's current location."""

        location = self.current_location()

        if location is None:
            return []

        return [
            self.world.interactables[interactable_id]
            for interactable_id in location.interactables
            if interactable_id in self.world.interactables
        ]