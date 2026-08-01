from .state import GameState, Location, Interactable, NPC


def create_new_game() -> GameState:
    """Create a new game world."""

    game = GameState()

    house = Location(
        id="old_wooden_house",
        name="Old Wooden House",
        description=(
            "An old wooden house surrounded by damp forest. "
            "Rain taps steadily against the roof."
        ),
        exits={
            "outside": "forest_edge",
            "kitchen": "kitchen",
            "upstairs": "upstairs",
        },
        items=[
            "Rusty Key",
            "Torn Note",
        ],
        npcs=[
            "old_man",
        ],
        interactables=[],
        symbol="🏠",
        visual_type="house",
    )

    forest_edge = Location(
        id="forest_edge",
        name="Forest Edge",
        description=(
            "The forest begins here, dense with wet trees and "
            "thick undergrowth. Rain falls steadily through the canopy."
        ),
        exits={
            "house": "old_wooden_house",
            "forest": "deep_forest",
        },
        symbol="🌲",
        visual_type="forest",
    )

    kitchen = Location(
        id="kitchen",
        name="Kitchen",
        description=(
            "A dusty old kitchen with wooden cabinets, "
            "a cold fireplace, and a table covered in forgotten things."
        ),
        exits={
            "outside": "old_wooden_house",
        },
        symbol="🍳",
        visual_type="interior",
    )

    upstairs = Location(
        id="upstairs",
        name="Upstairs Hall",
        description=(
            "A narrow wooden hallway stretches across the upper floor. "
            "Several old doors line the walls. One particularly old door "
            "stands at the far end of the hallway."
        ),
        exits={
            "downstairs": "old_wooden_house",
        },
        interactables=[
            "locked_upstairs_door",
        ],
        symbol="🚪",
        visual_type="interior",
    )

    deep_forest = Location(
        id="deep_forest",
        name="Deep Forest",
        description=(
            "The trees grow thicker here, blocking much of the daylight. "
            "The forest seems to stretch endlessly into the distance."
        ),
        exits={
            "back": "forest_edge",
        },
        symbol="🌳",
        visual_type="forest",
    )

    locked_upstairs_door = Interactable(
        id="locked_upstairs_door",
        name="Locked Upstairs Door",
        description=(
            "A weathered wooden door stands at the end of the hallway. "
            "Its old brass lock is dark with age, and a small keyhole "
            "suggests that a key may still open it."
        ),
        location="upstairs",
        state="locked",
        unlock_items=["Rusty Key"],
    )

    old_man = NPC(
        id="old_man",
        name="Old Man",
        location="old_wooden_house",
        description=(
            "An elderly man sits by the fireplace, warming his hands "
            "over the low flames. His eyes are tired but kind."
        ),
        disposition=10,
        personality=[
            "kind",
            "cautious",
            "reserved",
        ],
        knowledge=[
            "The house has an upstairs floor.",
            "The house has been here for many years.",
            "The upstairs door is old and has a lock.",
            "The northern road leads toward the forest.",
        ],
        beliefs=[
            "Nobody has entered the upstairs room recently.",
            "The house is probably safe despite its age.",
            "The forest is likely quiet this time of day.",
        ],
    )

    game.world.locations = {
        house.id: house,
        forest_edge.id: forest_edge,
        kitchen.id: kitchen,
        upstairs.id: upstairs,
        deep_forest.id: deep_forest,
    }

    game.world.interactables = {
        locked_upstairs_door.id: locked_upstairs_door,
    }

    game.world.npcs = {
        old_man.id: old_man,
    }

    game.player.location = house.id

    return game


def add_generated_location(
    game: GameState,
    location: Location,
) -> bool:
    """Add a procedurally generated location to the world."""

    if not location.id:
        return False

    if location.id in game.world.locations:
        return False

    game.world.locations[location.id] = location

    return True
