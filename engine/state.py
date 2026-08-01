from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Player:
    name: str = "Traveler"
    hp: int = 100
    max_hp: int = 100
    location: str = "old_wooden_house"
    inventory: List[str] = field(
        default_factory=lambda: ["Rusty Key", "Torn Note"]
    )


@dataclass
class NPC:
    id: str
    name: str
    location: str
    disposition: int = 0
    memory: List[str] = field(default_factory=list)


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


@dataclass
class World:
    name: str = "Unnamed World"
    genre: str = "Fantasy"
    time: str = "12:00"
    day: int = 1
    weather: str = "Rain"
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