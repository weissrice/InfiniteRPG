import re
from typing import Any, Dict

from .state import GameState, Interactable, NPC
from .generation import generate_location
from .routines import advance_npc_routines, update_npc_activities
from .world import add_generated_location


class ActionResult:
    def __init__(
        self,
        success: bool,
        message: str,
        data: Dict[str, Any] | None = None,
    ):
        self.success = success
        self.message = message
        self.data = data or {}


def move_player(
    game: GameState,
    destination: str,
    ai=None,
) -> ActionResult:
    """Move the player to an existing or newly generated location."""

    location = game.current_location()

    if location is None:
        return ActionResult(
            False,
            "You are somewhere that does not exist.",
        )

    destination_lower = destination.lower().strip()

    for direction, target_id in location.exits.items():
        target = game.world.locations.get(target_id)

        if direction.lower() == destination_lower:
            game.player.location = target_id

            return ActionResult(
                True,
                f"You move to {target.name if target else target_id}.",
                {"location": target_id},
            )

        if target_id.lower() == destination_lower:
            game.player.location = target_id

            return ActionResult(
                True,
                f"You move to {target.name if target else target_id}.",
                {"location": target_id},
            )

        if target and target.name.lower() == destination_lower:
            game.player.location = target_id

            return ActionResult(
                True,
                f"You move to {target.name}.",
                {"location": target_id},
            )

    aliases = {
        "outside": {
            "outside",
            "out",
            "outdoors",
            "leave",
            "leave the house",
        },
        "house": {
            "inside",
            "in",
            "indoors",
            "house",
            "home",
            "go inside",
            "go in the house",
            "go into the house",
        },
        "forest": {
            "forest",
            "woods",
        },
        "upstairs": {
            "upstairs",
            "up",
        },
        "downstairs": {
            "downstairs",
            "down",
        },
    }

    for direction, target_id in location.exits.items():
        direction_lower = direction.lower()

        if direction_lower not in aliases:
            continue

        for alias in aliases[direction_lower]:
            if alias == destination_lower:
                game.player.location = target_id
                target = game.world.locations.get(target_id)

                return ActionResult(
                    True,
                    f"You move to {target.name if target else target_id}.",
                    {"location": target_id},
                )

    for direction, target_id in location.exits.items():
        if direction.lower() in destination_lower:
            game.player.location = target_id
            target = game.world.locations.get(target_id)

            return ActionResult(
                True,
                f"You move to {target.name if target else target_id}.",
                {"location": target_id},
            )

    for direction, target_id in location.exits.items():
        target = game.world.locations.get(target_id)

        if target is None:
            continue

        if target.name.lower() in destination_lower:
            game.player.location = target_id

            return ActionResult(
                True,
                f"You move to {target.name}.",
                {"location": target_id},
            )

    if ai is not None:
        generated = generate_location(
            game,
            ai,
            destination_lower,
        )

        if generated is not None:
            game.player.location = generated.id

            return ActionResult(
                True,
                f"You discover {generated.name}.",
                {
                    "location": generated.id,
                    "generated": True,
                },
            )

    return ActionResult(
        False,
        f"You cannot go to '{destination}' from here.",
    )


def _find_interactable(
    game: GameState,
    target: str,
) -> Interactable | None:
    """Find an interactable object at the player's current location."""

    location = game.current_location()

    if location is None:
        return None

    target_lower = target.lower().strip()

    for object_id in location.interactables:
        obj = game.world.interactables.get(object_id)

        if obj is None:
            continue

        if (
            obj.id.lower() == target_lower
            or obj.name.lower() == target_lower
            or target_lower in obj.name.lower()
            or obj.name.lower() in target_lower
        ):
            return obj

    return None


MAX_NPC_MEMORY = 20


def _record_npc_memory(
    npc: NPC,
    entry: str,
) -> None:
    """Record a compact, deduplicated memory entry on an NPC."""

    if entry not in npc.memory:
        npc.memory.append(entry)

    if len(npc.memory) > MAX_NPC_MEMORY:
        del npc.memory[:-MAX_NPC_MEMORY]


def _find_npc(
    game: GameState,
    target: str,
) -> NPC | None:
    """Find an NPC at the player's current location."""

    location = game.current_location()

    if location is None:
        return None

    target_lower = target.lower().strip()

    for npc_id in location.npcs:
        npc = game.world.npcs.get(npc_id)

        if npc is None:
            continue

        if (
            npc.id.lower() == target_lower
            or npc.name.lower() == target_lower
            or target_lower in npc.name.lower()
            or npc.name.lower() in target_lower
        ):
            return npc

    return None


def _find_any_npc(
    game: GameState,
    target: str,
) -> NPC | None:
    """Find an NPC by id or name anywhere in the world."""

    target_lower = target.lower().strip()

    for npc in game.world.npcs.values():
        if (
            npc.id.lower() == target_lower
            or npc.name.lower() == target_lower
            or target_lower in npc.name.lower()
            or npc.name.lower() in target_lower
        ):
            return npc

    return None


def _find_interactable_at_location(
    game: GameState,
    location_id: str,
    target: str,
) -> Interactable | None:
    """Find an interactable object at a specific location."""

    location = game.world.locations.get(location_id)

    if location is None:
        return None

    target_lower = target.lower().strip()

    for object_id in location.interactables:
        obj = game.world.interactables.get(object_id)

        if obj is None:
            continue

        if (
            obj.id.lower() == target_lower
            or obj.name.lower() == target_lower
            or target_lower in obj.name.lower()
            or obj.name.lower() in target_lower
        ):
            return obj

    return None


def _extract_response_summary(
    npc_name: str,
    narration: str,
) -> str | None:
    """Build a concise third-person memory entry from an NPC's narration.

    Returns None when no reliable summary can be produced so the caller
    can fall back to storing only the topic/question memory.
    """

    if not narration:
        return None

    quoted = re.findall(r'"[^"]*"|\'[^\']*\'', narration)

    if not quoted:
        return None

    spoken = max(quoted, key=len)[1:-1].strip()

    if len(spoken) < 3:
        return None

    spoken = re.sub(r"\s+", " ", spoken)
    spoken = spoken.rstrip(".!?…").strip()

    if not spoken:
        return None

    # A spoken question cannot be summarized cleanly as a statement.
    if any(
        spoken.lower().startswith(word)
        for word in (
            "do ", "does ", "did ", "is ", "are ", "am ", "was ",
            "were ", "can ", "could ", "will ", "would ", "should ",
            "what ", "why ", "who ", "where ", "when ", "how ",
            "have ", "has ", "had ",
        )
    ):
        return None

    lower = spoken.lower()

    for old, new in (
        ("i am ", "he is "),
        ("i'm ", "he is "),
        ("i have ", "he has "),
        ("i've ", "he has "),
        ("i was ", "he was "),
        ("i think ", "he thinks "),
        ("i believe ", "he believes "),
        ("i feel ", "he feels "),
        ("i expect ", "he expects "),
        ("i'd ", "he would "),
        ("i'll ", "he will "),
        ("i ", "he "),
    ):
        if lower.startswith(old):
            spoken = new + spoken[len(old):]
            break
    else:
        spoken = spoken[:1].lower() + spoken[1:]

    return f"{npc_name} told the player that {spoken}."


def record_conversation_response(
    game: GameState,
    target: str,
    narration: str,
) -> str | None:
    """Record a concise summary of an NPC's spoken response, if extractable.

    Returns the stored memory entry, or None if no NPC matched or no
    reliable summary could be extracted.
    """

    npc = _find_npc(game, target)

    if npc is None:
        return None

    entry = _extract_response_summary(npc.name, narration)

    if entry is None:
        return None

    _record_npc_memory(npc, entry)

    return entry


def interact(
    game: GameState,
    target: str,
    topic: str = "",
) -> ActionResult:
    """Interact with an object or NPC at the current location."""

    obj = _find_interactable(game, target)

    if obj is not None:
        obj.discovered = True

        if obj.state == "locked":
            return ActionResult(
                True,
                (
                    f"The {obj.name.lower()} is locked. "
                    "You notice an old keyhole."
                ),
                {
                    "interactable": obj.id,
                    "state": obj.state,
                    "discovered": True,
                },
            )

        if obj.state == "unlocked":
            return ActionResult(
                True,
                f"The {obj.name.lower()} is unlocked.",
                {
                    "interactable": obj.id,
                    "state": obj.state,
                    "discovered": True,
                },
            )

        if not obj.memory:
            obj.memory.append(
                "The player interacted with this object."
            )

        return ActionResult(
            True,
            obj.description,
            {
                "interactable": obj.id,
                "state": obj.state,
                "discovered": True,
            },
        )

    npc = _find_npc(game, target)

    if npc is not None:
        topic_lower = topic.lower().strip()

        if topic_lower:
            _record_npc_memory(
                npc,
                f"The player asked {npc.name} about "
                f"{topic_lower}.",
            )
        else:
            _record_npc_memory(
                npc,
                f"The player spoke with {npc.name}.",
            )

        return ActionResult(
            True,
            (
                f"You speak to {npc.name}. "
                f"{npc.description}"
            ),
            {
                "npc": npc.id,
                "name": npc.name,
                "disposition": npc.disposition,
                "memory": list(npc.memory),
            },
        )

    return ActionResult(
        False,
        f"You cannot find '{target}' here.",
    )


def npc_interact(
    game: GameState,
    actor: str,
    target: str,
    topic: str = "",
) -> ActionResult:
    """Handle an NPC-initiated interact (dialogue) event.

    V1 supports only an NPC addressing another entity at the current
    location. Python remains authoritative: the actor must exist, be an
    NPC, and be at the current location.
    """

    npc = _find_any_npc(game, actor)

    if npc is None:
        return ActionResult(
            False,
            f"NPC actor '{actor}' does not exist.",
        )

    location = game.current_location()

    if location is None or npc.id not in location.npcs:
        return ActionResult(
            False,
            f"{npc.name} is not at the current location.",
        )

    player = game.player
    target_lower = target.lower().strip()

    target_is_player = (
        target_lower in {"traveler", "player", "you", "me"}
        or (
            target_lower
            and (
                target_lower in player.name.lower()
                or player.name.lower() in target_lower
            )
        )
    )

    if target_is_player:
        target_label = "the player"
        target_data = player.name
    else:
        target_npc = _find_npc(game, target)

        if target_npc is None:
            return ActionResult(
                False,
                f"{npc.name} cannot find target '{target}' here.",
            )

        target_label = target_npc.name
        target_data = target_label

    topic_lower = topic.lower().strip()

    if topic_lower:
        _record_npc_memory(
            npc,
            f"{npc.name} spoke to {target_label} about {topic_lower}.",
        )
    else:
        _record_npc_memory(
            npc,
            f"{npc.name} spoke to {target_label}.",
        )

    return ActionResult(
        True,
        (
            f"{npc.name} speaks to {target_label}"
            + (f" about {topic_lower}." if topic_lower else ".")
        ),
        {
            "actor": npc.id,
            "target": target_data,
            "topic": topic_lower,
        },
    )


def npc_interact_object(
    game: GameState,
    actor: str,
    target: str,
) -> ActionResult:
    """Handle an NPC-initiated interaction with a world object.

    V1: the actor must be an NPC at the current location, the target
    must be an interactable object at that location, and the target
    must equal the NPC's current activity object. The effect is
    memory-only; Python never mutates the object's state, flags, items,
    doors, or locations.
    """

    npc = _find_any_npc(game, actor)

    if npc is None:
        return ActionResult(
            False,
            f"NPC actor '{actor}' does not exist.",
        )

    location = game.current_location()

    if location is None or npc.id not in location.npcs:
        return ActionResult(
            False,
            f"{npc.name} is not at the current location.",
        )

    target_lower = target.lower().strip()

    if not target_lower:
        return ActionResult(
            False,
            f"{npc.name} cannot interact with an empty target.",
        )

    obj = _find_interactable_at_location(
        game,
        location.id,
        target,
    )

    if obj is None:
        return ActionResult(
            False,
            f"{npc.name} cannot find '{target}' here.",
        )

    if obj.id != npc.current_activity_object:
        return ActionResult(
            False,
            (
                f"{npc.name} is not currently working with "
                f"the {obj.name.lower()}."
            ),
        )

    _record_npc_memory(
        npc,
        f"{npc.name} used the {obj.name}.",
    )

    entry = f"{npc.name} used this."

    if entry not in obj.memory:
        obj.memory.append(entry)

    return ActionResult(
        True,
        f"{npc.name} uses the {obj.name}.",
        {
            "actor": npc.id,
            "target": obj.id,
            "state": obj.state,
        },
    )


def open_interactable(
    game: GameState,
    target: str,
    ai=None,
) -> ActionResult:
    """Open an interactable object (e.g., a door)."""
    obj = _find_interactable(game, target)

    if obj is None:
        return ActionResult(
            False,
            f"You cannot find '{target}' here.",
        )

    obj.discovered = True

    if obj.state == "locked":
        return ActionResult(
            False,
            f"The {obj.name.lower()} is locked.",
            {
                "interactable": obj.id,
                "state": obj.state,
                "discovered": True,
            },
        )

    if obj.state == "open":
        return ActionResult(
            True,
            f"The {obj.name.lower()} is already open.",
            {
                "interactable": obj.id,
                "state": obj.state,
                "discovered": True,
            },
        )

    if obj.state == "unlocked":
        obj.state = "open"
        obj.used = True

        obj.memory.append("The player opened this door.")

        # Try to generate a location beyond the door if not already connected
        location = game.current_location()
        if location is not None:
            # Check if there's already an exit for this door
            door_direction = obj.id.replace("_door", "").replace("locked_", "").replace("upstairs_", "")
            if not door_direction:
                door_direction = "door"

            # Check if exit already exists
            if door_direction not in location.exits:
                # Generate a new location beyond the door
                if ai is not None:
                    generated = generate_location(game, ai, door_direction)
                    if generated is not None:
                        # Add exit from current location to generated location
                        location.exits[door_direction] = generated.id
                        # Add return exit
                        generated.exits["back"] = location.id

                        return ActionResult(
                            True,
                            f"You open the {obj.name.lower()}, revealing {generated.name} beyond.",
                            {
                                "interactable": obj.id,
                                "state": obj.state,
                                "discovered": True,
                                "opened": True,
                                "leads_to": generated.id,
                            },
                        )

        return ActionResult(
            True,
            f"You open the {obj.name.lower()}.",
            {
                "interactable": obj.id,
                "state": obj.state,
                "discovered": True,
                "opened": True,
            },
        )

    # Default interaction for other states
    if not obj.memory:
        obj.memory.append("The player interacted with this object.")

    return ActionResult(
        True,
        obj.description,
        {
            "interactable": obj.id,
            "state": obj.state,
            "discovered": True,
        },
    )


def use_item(
    game: GameState,
    item_name: str,
    target: str = "",
) -> ActionResult:
    """Use an inventory item, optionally on an interactable object."""

    item_lower = item_name.lower().strip()

    matching_item = None

    for item in game.player.inventory:
        if (
            item.lower() == item_lower
            or item_lower in item.lower()
        ):
            matching_item = item
            break

    if matching_item is None:
        return ActionResult(
            False,
            f"You do not have '{item_name}'.",
        )

    location = game.current_location()

    if location is None:
        return ActionResult(
            False,
            "You are nowhere.",
        )

    target_lower = target.lower().strip()

    matching_object: Interactable | None = None

    print()
    print("DEBUG USE ITEM")
    print(f"Item: {matching_item}")
    print(f"Target requested: {target_lower}")
    print(f"Current location: {location.id}")
    print(f"Interactables here: {location.interactables}")
    print()

    if target_lower:
        for object_id in location.interactables:
            obj = game.world.interactables.get(object_id)

            if obj is None:
                continue

            object_id_lower = obj.id.lower()
            object_name_lower = obj.name.lower()

            if (
                object_id_lower == target_lower
                or object_name_lower == target_lower
                or target_lower in object_name_lower
                or object_name_lower in target_lower
                or all(
                    word in object_name_lower
                    for word in target_lower.split()
                    )
            ):
                matching_object = obj
                break

        if matching_object is None:
            return ActionResult(
                False,
                f"You cannot find '{target}' here.",
            )

    # ---------------------------------------------------------
    # DYNAMIC ITEM + OBJECT INTERACTION
    # ---------------------------------------------------------

    if matching_object is not None:
        matching_object.discovered = True

        print()
        print("DEBUG USE ITEM ON OBJECT")
        print(f"Item: {matching_item}")
        print(f"Target: {matching_object.id}")
        print(f"Target state: {matching_object.state}")
        print(f"Unlock items for target: {matching_object.unlock_items}")
        print()

        if matching_object.state == "locked":
            can_unlock = any(
                item.lower() == matching_item.lower()
                for item in matching_object.unlock_items
            )

            if not can_unlock:
                matching_object.memory.append(
                    f"The player tried to use {matching_item}, "
                    "but it did not unlock the object."
                )

                return ActionResult(
                    False,
                    (
                        f"The {matching_object.name.lower()} is locked. "
                        f"The {matching_item} does not fit."
                    ),
                    {
                        "item": matching_item,
                        "target": matching_object.id,
                        "state": matching_object.state,
                        "discovered": True,
                    },
                )

            matching_object.state = "unlocked"
            matching_object.used = True

            game.player.inventory.remove(matching_item)

            matching_object.memory.append(
                f"The player unlocked this object with the "
                f"{matching_item}."
            )

            return ActionResult(
                True,
                (
                    f"You use the {matching_item} on "
                    f"the {matching_object.name}. "
                    "The lock clicks open."
                ),
                {
                    "item": matching_item,
                    "target": matching_object.id,
                    "state": matching_object.state,
                    "used": True,
                    "consumed": True,
                },
            )

        matching_object.used = True

        matching_object.memory.append(
            f"The player used {matching_item} on the object."
        )

        return ActionResult(
            True,
            (
                f"You use the {matching_item} on "
                f"the {matching_object.name}."
            ),
            {
                "item": matching_item,
                "target": matching_object.id,
                "state": matching_object.state,
                "used": True,
            },
        )

    return ActionResult(
        True,
        f"You use the {matching_item}.",
        {
            "item": matching_item,
            "used": True,
        },
    )



def take_item(
    game: GameState,
    item_name: str,
) -> ActionResult:
    location = game.current_location()

    if location is None:
        return ActionResult(False, "You are nowhere.")

    matching_item = None

    for item in location.items:
        if item.lower() == item_name.lower():
            matching_item = item
            break

    if matching_item is None:
        return ActionResult(
            False,
            f"There is no '{item_name}' here.",
        )

    location.items.remove(matching_item)
    game.player.inventory.append(matching_item)

    return ActionResult(
        True,
        f"You take the {matching_item}.",
        {"item": matching_item},
    )


def drop_item(
    game: GameState,
    item_name: str,
) -> ActionResult:
    location = game.current_location()

    if location is None:
        return ActionResult(False, "You are nowhere.")

    matching_item = None

    for item in game.player.inventory:
        if item.lower() == item_name.lower():
            matching_item = item
            break

    if matching_item is None:
        return ActionResult(
            False,
            f"You do not have '{item_name}'.",
        )

    game.player.inventory.remove(matching_item)
    location.items.append(matching_item)

    return ActionResult(
        True,
        f"You drop the {matching_item}.",
        {"item": matching_item},
    )


def inspect(
    game: GameState,
    target: str,
) -> ActionResult:
    """Inspect a location, item, or interactable object."""

    location = game.current_location()

    if location is None:
        return ActionResult(
            False,
            "There is nothing around you.",
        )

    target_lower = target.lower().strip()

    # Inspect the current location.
    if target_lower in {
        "room",
        "area",
        "surroundings",
        location.name.lower(),
    }:
        return ActionResult(
            True,
            location.description,
        )

    # Inspect an item on the ground.
    for item in location.items:
        if (
            item.lower() == target_lower
            or target_lower in item.lower()
        ):
            return ActionResult(
                True,
                f"You examine the {item}.",
                {"target": item},
            )

    # Inspect an interactable object.
    for object_id in location.interactables:
        obj = game.world.interactables.get(object_id)

        if obj is None:
            continue

        object_id_lower = obj.id.lower()
        object_name_lower = obj.name.lower()

        if (
            object_id_lower == target_lower
            or object_name_lower == target_lower
            or target_lower in object_name_lower
            or object_name_lower in target_lower
        ):
            obj.discovered = True

            return ActionResult(
                True,
                obj.description,
                {
                    "interactable": obj.id,
                    "discovered": True,
                    "state": obj.state,
                },
            )

    return ActionResult(
        True,
        f"You examine {target}, but notice nothing unusual.",
        {"target": target},
    )



def wait(
    game: GameState,
    minutes: int = 10,
) -> ActionResult:
    if minutes <= 0:
        return ActionResult(
            False,
            "You cannot wait for that amount of time.",
        )

    total_minutes = (
        game.world.day * 24 * 60
        + _time_to_minutes(game.world.time)
        + minutes
    )

    game.world.day = total_minutes // (24 * 60)

    remaining = total_minutes % (24 * 60)

    hours = remaining // 60
    mins = remaining % 60

    game.world.time = f"{hours:02d}:{mins:02d}"

    routine_changes = advance_npc_routines(game)
    activity_changes = update_npc_activities(game)

    data = {"minutes": minutes}

    if routine_changes:
        data["routine_changes"] = routine_changes

    if activity_changes:
        data["activity_changes"] = activity_changes

    return ActionResult(
        True,
        f"You wait for {minutes} minutes.",
        data,
    )


def _time_to_minutes(time_string: str) -> int:
    try:
        hours, minutes = time_string.split(":")
        return int(hours) * 60 + int(minutes)
    except (ValueError, TypeError):
        return 0
