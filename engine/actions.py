import re
from typing import Any, Dict

from .state import GameState, Interactable, NPC, Quest, QuestObjective
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
            game.visited_locations.add(target_id)
            quest_events = _check_quest_progress(
                game, "visit", target_id,
            )

            return ActionResult(
                True,
                f"You move to {target.name if target else target_id}.",
                {
                    "location": target_id,
                    "quest_events": quest_events if quest_events else [],
                },
            )

        if target_id.lower() == destination_lower:
            game.player.location = target_id
            game.visited_locations.add(target_id)
            quest_events = _check_quest_progress(
                game, "visit", target_id,
            )

            return ActionResult(
                True,
                f"You move to {target.name if target else target_id}.",
                {
                    "location": target_id,
                    "quest_events": quest_events if quest_events else [],
                },
            )

        if target and target.name.lower() == destination_lower:
            game.player.location = target_id
            game.visited_locations.add(target_id)
            quest_events = _check_quest_progress(
                game, "visit", target_id,
            )

            return ActionResult(
                True,
                f"You move to {target.name}.",
                {
                    "location": target_id,
                    "quest_events": quest_events if quest_events else [],
                },
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
                quest_events = _check_quest_progress(
                    game, "visit", target_id,
                )

                return ActionResult(
                    True,
                    f"You move to {target.name if target else target_id}.",
                    {
                        "location": target_id,
                        "quest_events": (
                            quest_events if quest_events else []
                        ),
                    },
                )

    for direction, target_id in location.exits.items():
        if direction.lower() in destination_lower:
            game.player.location = target_id
            target = game.world.locations.get(target_id)
            quest_events = _check_quest_progress(
                game, "visit", target_id,
            )

            return ActionResult(
                True,
                f"You move to {target.name if target else target_id}.",
                {
                    "location": target_id,
                    "quest_events": quest_events if quest_events else [],
                },
            )

    for direction, target_id in location.exits.items():
        target = game.world.locations.get(target_id)

        if target is None:
            continue

        if target.name.lower() in destination_lower:
            game.player.location = target_id
            quest_events = _check_quest_progress(
                game, "visit", target_id,
            )

            return ActionResult(
                True,
                f"You move to {target.name}.",
                {
                    "location": target_id,
                    "quest_events": quest_events if quest_events else [],
                },
            )

    if ai is not None:
        generated = generate_location(
            game,
            ai,
            destination_lower,
        )

        if generated is not None:
            game.player.location = generated.id
            quest_events = _check_quest_progress(
                game, "visit", generated.id,
            )

            return ActionResult(
                True,
                f"You discover {generated.name}.",
                {
                    "location": generated.id,
                    "generated": True,
                    "quest_events": quest_events if quest_events else [],
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


RELATIONSHIP_MIN = -100
RELATIONSHIP_MAX = 100
CONVERSATION_RELATIONSHIP_DELTA = 1


def _clamp(value: int, low: int, high: int) -> int:
    """Clamp an integer to the inclusive [low, high] range."""

    return max(low, min(high, value))


def _adjust_relationship(
    npc: NPC,
    other_name: str,
    delta: int,
) -> int:
    """Apply a bounded relationship delta toward another character.

    The score is directional: only this NPC's attitude toward
    ``other_name`` changes. Returns the updated score.
    """

    current = npc.relationships.get(other_name, 0)

    updated = _clamp(
        current + delta,
        RELATIONSHIP_MIN,
        RELATIONSHIP_MAX,
    )

    npc.relationships[other_name] = updated

    return updated


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

        # Quest: talk objective progress
        quest_events = _check_quest_progress(
            game, "talk", npc.id,
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
                "quest_events": quest_events if quest_events else [],
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
    knowledge_transfer: str = "",
    belief_transfer: str = "",
    goal_transfer: str = "",
) -> ActionResult:
    """Handle an NPC-initiated interact (dialogue) event.

    V1 supports only an NPC addressing another entity at the current
    location. Python remains authoritative: the actor must exist, be an
    NPC, and be at the current location.

    A genuinely new NPC-to-NPC conversation (the initiation memory entry
    is not yet recorded) additionally advances both directional
    relationship edges by a fixed, bounded increment. This deterministic
    mutation is the only way relationship scores change in this feature.
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

        if target_npc.id == npc.id:
            return ActionResult(
                False,
                f"{npc.name} cannot talk to itself.",
            )

        target_label = target_npc.name
        target_data = target_label

    topic_lower = topic.lower().strip()
    relationship_update = None

    if topic_lower:
        initiator_entry = (
            f"{npc.name} spoke to {target_label} about {topic_lower}."
        )
    else:
        initiator_entry = f"{npc.name} spoke to {target_label}."

    is_new_event = initiator_entry not in npc.memory

    _record_npc_memory(npc, initiator_entry)

    if not target_is_player:
        if topic_lower:
            _record_npc_memory(
                target_npc,
                f"{npc.name} spoke with {target_npc.name} about {topic_lower}.",
            )
        else:
            _record_npc_memory(
                target_npc,
                f"{npc.name} spoke with {target_npc.name}.",
            )

    if is_new_event and not target_is_player:
        actor_score = _adjust_relationship(
            npc,
            target_npc.name,
            CONVERSATION_RELATIONSHIP_DELTA,
        )
        target_score = _adjust_relationship(
            target_npc,
            npc.name,
            CONVERSATION_RELATIONSHIP_DELTA,
        )

        relationship_update = {
            "delta": CONVERSATION_RELATIONSHIP_DELTA,
            "target": target_npc.name,
            "actor_score": actor_score,
            "target_score": target_score,
        }

    knowledge_update = None

    if (
        knowledge_transfer
        and not target_is_player
        and is_new_event
    ):
        kt_lower = knowledge_transfer.strip()
        if (
            kt_lower
            and kt_lower in npc.knowledge
            and kt_lower not in target_npc.knowledge
        ):
            target_npc.knowledge.append(kt_lower)
            knowledge_update = {"knowledge": kt_lower}

    belief_update = None

    if (
        belief_transfer
        and not target_is_player
        and is_new_event
    ):
        bt_lower = belief_transfer.strip()
        if (
            bt_lower
            and bt_lower in npc.beliefs
            and bt_lower not in target_npc.beliefs
        ):
            target_npc.beliefs.append(bt_lower)
            belief_update = {"belief": bt_lower}

    goal_update = None

    if (
        goal_transfer
        and not target_is_player
        and is_new_event
    ):
        gt_lower = goal_transfer.strip()
        if (
            gt_lower
            and gt_lower in npc.goals
            and gt_lower not in target_npc.goals
        ):
            target_npc.goals.append(gt_lower)
            goal_update = {"goal": gt_lower}

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
            "relationship_update": relationship_update,
            "knowledge_update": knowledge_update,
            "belief_update": belief_update,
            "goal_update": goal_update,
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

    # Quest: find objective progress
    quest_events = _check_quest_progress(
        game, "find", matching_item,
    )

    return ActionResult(
        True,
        f"You take the {matching_item}.",
        {
            "item": matching_item,
            "quest_events": quest_events if quest_events else [],
        },
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

    old_total = (
        game.world.day * 24 * 60
        + _time_to_minutes(game.world.time)
    )

    new_total = old_total + minutes

    game.world.day = new_total // (24 * 60)

    remaining = new_total % (24 * 60)

    hours = remaining // 60
    mins = remaining % 60

    game.world.time = f"{hours:02d}:{mins:02d}"

    from .weather import (
        compute_weather,
        get_weather_change_message,
        _weather_period,
    )

    old_condition = game.world.weather.condition

    if _weather_period(old_total) != _weather_period(new_total):
        new_weather = compute_weather(game.world.seed, new_total)
        game.world.weather = new_weather

    from .events import process_event_range

    event_messages = []
    new_events = process_event_range(game, old_total, new_total)
    for ev in new_events:
        event_messages.append(ev.description)

    routine_changes = advance_npc_routines(game)
    activity_changes = update_npc_activities(game)

    data: dict[str, Any] = {"minutes": minutes}

    weather_change = get_weather_change_message(
        old_condition, game.world.weather.condition,
    )

    if weather_change:
        data["weather_change"] = weather_change

    if event_messages:
        data["world_events"] = event_messages

    if routine_changes:
        data["routine_changes"] = routine_changes

    if activity_changes:
        data["activity_changes"] = activity_changes

    return ActionResult(
        True,
        f"You wait for {minutes} minutes.",
        data,
    )


# ---------------------------------------------------------
# COMBAT
# ---------------------------------------------------------

_WEAPON_KEYWORDS = frozenset({
    "sword",
    "axe",
    "knife",
    "blade",
    "club",
    "mace",
    "spear",
    "hammer",
})

PLAYER_BARE_HANDS_DAMAGE = 5
PLAYER_WEAPON_DAMAGE = 15
NPC_ATTACK_DAMAGE = 10

# Progression
XP_PER_LEVEL = 100
XP_PER_NPC_KILL = 50
XP_PER_CRAFT = 10

_VALID_STATS = frozenset({
    "strength", "vitality", "agility", "intelligence",
})

# Crafting & Trading
from .state import Recipe

RECIPES = {
    "health_potion": Recipe(
        id="health_potion",
        name="Health Potion",
        ingredients={"Herb": 2, "Empty Bottle": 1},
        output="Health Potion",
        output_quantity=1,
    ),
    "torch": Recipe(
        id="torch",
        name="Torch",
        ingredients={"Wood": 1, "Cloth": 1},
        output="Torch",
        output_quantity=1,
    ),
    "iron_sword": Recipe(
        id="iron_sword",
        name="Iron Sword",
        ingredients={"Iron Ore": 3, "Wood": 1},
        output="Iron Sword",
        output_quantity=1,
    ),
}

ITEM_PRICES = {
    "Herb": 5,
    "Empty Bottle": 10,
    "Health Potion": 30,
    "Iron Ore": 15,
    "Wood": 3,
    "Cloth": 5,
    "Iron Sword": 100,
    "Torch": 10,
    "Rusty Key": 0,
    "Torn Note": 0,
}

SELL_MULTIPLIER = 0.5


def _find_weapon(inventory: list[str], weapon_name: str) -> str | None:
    """Return the matching inventory item if it is a recognized weapon.

    Returns the original inventory string on match, or None.
    """

    weapon_lower = weapon_name.lower().strip()

    if not weapon_lower:
        return None

    for item in inventory:
        if item.lower() == weapon_lower:
            if any(kw in item.lower() for kw in _WEAPON_KEYWORDS):
                return item

    for item in inventory:
        if weapon_lower in item.lower():
            if any(kw in item.lower() for kw in _WEAPON_KEYWORDS):
                return item

    return None


def _apply_damage(target_hp: int, target_max_hp: int, damage: int):
    """Subtract damage from HP, clamp to 0, return (new_hp, is_dead)."""

    new_hp = max(0, target_hp - damage)
    return new_hp, new_hp <= 0


# ---------------------------------------------------------
# PROGRESSION
# ---------------------------------------------------------


def _recalculate_max_hp(game: GameState) -> None:
    """Derive max_hp from Vitality. Adjust current HP proportionally."""

    player = game.player
    new_max = 100 + ((player.vitality - 10) * 5)
    new_max = max(1, new_max)

    if new_max != player.max_hp:
        delta = new_max - player.max_hp
        player.max_hp = new_max
        player.hp = min(player.hp + delta, player.max_hp)


def _process_level_ups(game: GameState) -> dict:
    """Process all pending level-ups. Returns progression data dict."""

    player = game.player
    level_ups = 0

    while player.xp >= player.level * XP_PER_LEVEL:
        player.level += 1
        player.stat_points += 1
        level_ups += 1

    if level_ups == 0:
        return {
            "level_ups": 0,
            "new_level": player.level,
            "stat_points_gained": 0,
        }

    return {
        "level_ups": level_ups,
        "new_level": player.level,
        "stat_points_gained": level_ups,
    }


def _award_xp(
    game: GameState,
    amount: int,
    source: str = "",
) -> ActionResult:
    """Award XP to the player. Process level-ups. Return result."""

    if not isinstance(amount, (int, float)) or amount <= 0:
        return ActionResult(
            False,
            "Invalid XP amount.",
            {"reason": "invalid_xp_amount"},
        )

    amount = int(amount)
    player = game.player

    old_xp = player.xp
    old_level = player.level
    old_stat_points = player.stat_points

    player.xp += amount

    level_data = _process_level_ups(game)

    levels_gained = level_data["level_ups"]
    stat_points_gained = level_data["stat_points_gained"]

    message = f"Gained {amount} XP."
    if levels_gained > 0:
        message += (
            f" Level up! Now level {player.level}."
            f" +{stat_points_gained} stat point(s)."
        )

    return ActionResult(
        True,
        message,
        {
            "xp_gained": amount,
            "xp_total": player.xp,
            "level": player.level,
            "level_ups": levels_gained,
            "stat_points": player.stat_points,
            "source": source,
        },
    )


def allocate_stat(
    game: GameState,
    stat: str,
    amount: int = 1,
) -> ActionResult:
    """Allocate stat points to a player attribute."""

    player = game.player

    if not stat or stat.lower() not in _VALID_STATS:
        return ActionResult(
            False,
            f"Invalid stat. Valid stats: {sorted(_VALID_STATS)}.",
            {"reason": "invalid_stat"},
        )

    stat = stat.lower()

    if not isinstance(amount, (int, float)) or amount <= 0:
        return ActionResult(
            False,
            "Amount must be a positive integer.",
            {"reason": "invalid_amount"},
        )

    amount = int(amount)

    if amount > player.stat_points:
        return ActionResult(
            False,
            f"Not enough stat points. Have {player.stat_points}.",
            {"reason": "insufficient_stat_points"},
        )

    old_value = getattr(player, stat)
    old_max_hp = player.max_hp
    old_hp = player.hp

    player.stat_points -= amount
    setattr(player, stat, old_value + amount)

    # Apply derived effects
    if stat == "vitality":
        _recalculate_max_hp(game)

    hp_change = player.hp - old_hp

    message = (
        f"Allocated {amount} point(s) to {stat}."
        f" {stat.title()} is now {getattr(player, stat)}."
    )
    if stat == "vitality" and hp_change > 0:
        message += f" Max HP is now {player.max_hp}."

    return ActionResult(
        True,
        message,
        {
            "stat": stat,
            "amount": amount,
            "new_value": getattr(player, stat),
            "stat_points": player.stat_points,
            "max_hp": player.max_hp,
            "hp": player.hp,
        },
    )


# ---------------------------------------------------------
# CRAFTING & TRADING
# ---------------------------------------------------------


def craft(
    game: GameState,
    recipe_id: str,
) -> ActionResult:
    """Craft an item from a predefined recipe."""

    player = game.player

    recipe = RECIPES.get(recipe_id)
    if recipe is None:
        return ActionResult(
            False,
            f"Unknown recipe: {recipe_id}.",
            {"reason": "recipe_not_found"},
        )

    # Check ingredients
    missing = []
    insufficient = []

    for ingredient, required in recipe.ingredients.items():
        count = player.inventory.count(ingredient)
        if count == 0:
            missing.append(ingredient)
        elif count < required:
            insufficient.append(
                f"{ingredient} (have {count}, need {required})"
            )

    if missing or insufficient:
        reasons = []
        if missing:
            reasons.append(f"Missing: {', '.join(missing)}")
        if insufficient:
            reasons.append(f"Insufficient: {', '.join(insufficient)}")

        return ActionResult(
            False,
            f"Cannot craft {recipe.name}. {' '.join(reasons)}.",
            {"reason": "insufficient_ingredients"},
        )

    # Consume ingredients
    for ingredient, required in recipe.ingredients.items():
        for _ in range(required):
            player.inventory.remove(ingredient)

    # Add output
    for _ in range(recipe.output_quantity):
        player.inventory.append(recipe.output)

    # Award XP
    _award_xp(game, XP_PER_CRAFT, "crafting")

    return ActionResult(
        True,
        f"Crafted {recipe.output_quantity} {recipe.output}.",
        {
            "recipe_id": recipe.id,
            "recipe_name": recipe.name,
            "ingredients_consumed": dict(recipe.ingredients),
            "output": recipe.output,
            "output_quantity": recipe.output_quantity,
        },
    )


def buy_item(
    game: GameState,
    npc_id: str,
    item: str,
    quantity: int = 1,
) -> ActionResult:
    """Buy an item from an NPC."""

    player = game.player

    # Validate quantity
    if not isinstance(quantity, (int, float)) or quantity <= 0:
        return ActionResult(
            False,
            "Quantity must be a positive integer.",
            {"reason": "invalid_quantity"},
        )

    quantity = int(quantity)

    # Validate NPC exists
    npc = game.world.npcs.get(npc_id)
    if npc is None:
        return ActionResult(
            False,
            f"NPC '{npc_id}' not found.",
            {"reason": "npc_not_found"},
        )

    # Validate NPC is alive
    if npc.hp <= 0:
        return ActionResult(
            False,
            f"{npc.name} is dead.",
            {"reason": "npc_dead"},
        )

    # Validate NPC is co-located
    location = game.current_location()
    if location is None or npc_id not in location.npcs:
        return ActionResult(
            False,
            f"{npc.name} is not here.",
            {"reason": "npc_not_here"},
        )

    # Validate item has a price
    if item not in ITEM_PRICES or ITEM_PRICES[item] <= 0:
        return ActionResult(
            False,
            f"{item} is not for sale.",
            {"reason": "item_not_for_sale"},
        )

    # Validate NPC has item
    npc_count = npc.inventory.count(item)
    if npc_count < quantity:
        return ActionResult(
            False,
            f"{npc.name} doesn't have enough {item}.",
            {"reason": "insufficient_npc_stock"},
        )

    # Calculate price
    total_price = ITEM_PRICES[item] * quantity

    # Validate player has enough money
    if player.money < total_price:
        return ActionResult(
            False,
            f"Not enough money. Need {total_price}, have {player.money}.",
            {"reason": "insufficient_money"},
        )

    # Execute transaction
    for _ in range(quantity):
        npc.inventory.remove(item)
        player.inventory.append(item)

    player.money -= total_price
    npc.money += total_price

    return ActionResult(
        True,
        f"Bought {quantity} {item} for {total_price} gold.",
        {
            "npc_id": npc_id,
            "item": item,
            "quantity": quantity,
            "price": total_price,
            "player_money": player.money,
        },
    )


def sell_item(
    game: GameState,
    npc_id: str,
    item: str,
    quantity: int = 1,
) -> ActionResult:
    """Sell an item to an NPC."""

    player = game.player

    # Validate quantity
    if not isinstance(quantity, (int, float)) or quantity <= 0:
        return ActionResult(
            False,
            "Quantity must be a positive integer.",
            {"reason": "invalid_quantity"},
        )

    quantity = int(quantity)

    # Validate NPC exists
    npc = game.world.npcs.get(npc_id)
    if npc is None:
        return ActionResult(
            False,
            f"NPC '{npc_id}' not found.",
            {"reason": "npc_not_found"},
        )

    # Validate NPC is alive
    if npc.hp <= 0:
        return ActionResult(
            False,
            f"{npc.name} is dead.",
            {"reason": "npc_dead"},
        )

    # Validate NPC is co-located
    location = game.current_location()
    if location is None or npc_id not in location.npcs:
        return ActionResult(
            False,
            f"{npc.name} is not here.",
            {"reason": "npc_not_here"},
        )

    # Validate item has a price
    if item not in ITEM_PRICES or ITEM_PRICES[item] <= 0:
        return ActionResult(
            False,
            f"{item} cannot be sold.",
            {"reason": "item_not_sellable"},
        )

    # Validate player has item
    player_count = player.inventory.count(item)
    if player_count < quantity:
        return ActionResult(
            False,
            f"You don't have enough {item}.",
            {"reason": "insufficient_player_stock"},
        )

    # Calculate sell price
    sell_price = int(ITEM_PRICES[item] * SELL_MULTIPLIER) * quantity

    # Validate NPC has enough money
    if npc.money < sell_price:
        return ActionResult(
            False,
            f"{npc.name} doesn't have enough money.",
            {"reason": "insufficient_npc_money"},
        )

    # Execute transaction
    for _ in range(quantity):
        player.inventory.remove(item)
        npc.inventory.append(item)

    player.money += sell_price
    npc.money -= sell_price

    return ActionResult(
        True,
        f"Sold {quantity} {item} for {sell_price} gold.",
        {
            "npc_id": npc_id,
            "item": item,
            "quantity": quantity,
            "price": sell_price,
            "player_money": player.money,
        },
    )


def attack(
    game: GameState,
    attacker: str,
    target: str,
    weapon: str = "",
) -> ActionResult:
    """Execute a combat attack.

    ``attacker`` is ``"player"`` for player-initiated attacks, or an
    NPC id for NPC-initiated attacks.  ``target`` is an NPC id/name
    for player attacks, or ``"player"``/the player name for NPC attacks.
    """

    location = game.current_location()

    if location is None:
        return ActionResult(
            False,
            "You are nowhere.",
            {"attacker": attacker, "target": target,
             "reason": "no_location"},
        )

    is_player_attack = attacker == "player"

    # ----------------------------------------------------------
    # Resolve attacker
    # ----------------------------------------------------------

    attacker_npc = None

    if not is_player_attack:
        attacker_npc = _find_any_npc(game, attacker)

        if attacker_npc is None:
            return ActionResult(
                False,
                f"Attacker '{attacker}' does not exist.",
                {"attacker": attacker, "target": target,
                 "reason": "attacker_not_found"},
            )

        if attacker_npc.hp <= 0:
            return ActionResult(
                False,
                f"{attacker_npc.name} is already dead.",
                {"attacker": attacker, "target": target,
                 "reason": "attacker_dead"},
            )

        if attacker_npc.id not in location.npcs:
            return ActionResult(
                False,
                f"{attacker_npc.name} is not here.",
                {"attacker": attacker, "target": target,
                 "reason": "attacker_not_here"},
            )

    # ----------------------------------------------------------
    # Resolve target
    # ----------------------------------------------------------

    target_is_player = False
    target_npc = None

    target_lower = target.lower().strip()

    if is_player_attack:
        target_npc = _find_npc(game, target)

        if target_npc is None:
            return ActionResult(
                False,
                f"Target '{target}' is not here.",
                {"attacker": attacker, "target": target,
                 "reason": "target_not_found"},
            )

        if target_npc.hp <= 0:
            return ActionResult(
                False,
                f"{target_npc.name} is already dead.",
                {"attacker": attacker, "target": target,
                 "reason": "target_dead"},
            )
    else:
        target_is_player = (
            target_lower in {"traveler", "player", "you", "me"}
            or (
                target_lower
                and (
                    target_lower in game.player.name.lower()
                    or game.player.name.lower() in target_lower
                )
            )
        )

        if not target_is_player:
            return ActionResult(
                False,
                "NPCs can only attack the player in V1.",
                {"attacker": attacker, "target": target,
                 "reason": "invalid_target"},
            )

        if game.player.hp <= 0:
            return ActionResult(
                False,
                "The player is already dead.",
                {"attacker": attacker, "target": target,
                 "reason": "target_dead"},
            )

    # ----------------------------------------------------------
    # Self-target check
    # ----------------------------------------------------------

    if is_player_attack and target_npc is not None:
        pass
    elif not is_player_attack and target_is_player:
        pass
    else:
        return ActionResult(
            False,
            "Cannot attack yourself.",
            {"attacker": attacker, "target": target,
             "reason": "self_target"},
        )

    # ----------------------------------------------------------
    # Determine damage
    # ----------------------------------------------------------

    if is_player_attack:
        weapon_match = _find_weapon(game.player.inventory, weapon)
        if weapon_match:
            damage = PLAYER_WEAPON_DAMAGE
            used_weapon = weapon_match
        else:
            damage = PLAYER_BARE_HANDS_DAMAGE
            used_weapon = ""

        strength_mod = game.player.strength - 10
        damage += strength_mod
        damage = max(1, damage)
    else:
        damage = NPC_ATTACK_DAMAGE
        used_weapon = ""

    # ----------------------------------------------------------
    # Apply damage
    # ----------------------------------------------------------

    if is_player_attack and target_npc is not None:
        old_hp = target_npc.hp
        new_hp, is_dead = _apply_damage(
            target_npc.hp, target_npc.max_hp, damage,
        )
        target_npc.hp = new_hp

        _record_npc_memory(
            target_npc,
            f"The player attacked {target_npc.name}"
            + (f" with {used_weapon}." if used_weapon else "."),
        )

        for npc_id in location.npcs:
            witness = game.world.npcs.get(npc_id)
            if (
                witness
                and witness.id != target_npc.id
                and witness.hp > 0
            ):
                if is_dead:
                    _record_npc_memory(
                        witness,
                        f"The player killed {target_npc.name}.",
                    )
                else:
                    _record_npc_memory(
                        witness,
                        f"The player attacked {target_npc.name}.",
                    )

        if is_dead:
            if target_npc.id in location.npcs:
                location.npcs.remove(target_npc.id)

            # Quest: kill objective progress
            quest_events = _check_quest_progress(
                game, "kill", target_npc.id,
            )

            # Quest: fail quests where killed NPC was the giver
            for quest in game.quests.values():
                if quest.giver == target_npc.id:
                    _fail_quest(game, quest)

            # Progression: XP for kill
            xp_result = _award_xp(game, XP_PER_NPC_KILL, "npc_kill")

        else:
            quest_events = []
            xp_result = None

        result_xp = xp_result.data if is_dead and xp_result else {}

        return ActionResult(
            True,
            (
                f"You attack {target_npc.name}"
                + (f" with {used_weapon}" if used_weapon else "")
                + f" for {damage} damage."
                + (
                    f" {target_npc.name} is dead."
                    if is_dead
                    else ""
                )
            ),
            {
                "attacker": "player",
                "target": target_npc.id,
                "weapon": used_weapon,
                "damage": damage,
                "target_hp": target_npc.hp,
                "target_max_hp": target_npc.max_hp,
                "target_dead": is_dead,
                "quest_events": quest_events if quest_events else [],
                "xp": result_xp,
            },
        )

    # NPC attacks player
    if attacker_npc is not None:
        old_hp = game.player.hp
        new_hp, is_dead = _apply_damage(
            game.player.hp, game.player.max_hp, damage,
        )
        game.player.hp = new_hp

        _record_npc_memory(
            attacker_npc,
            f"{attacker_npc.name} attacked the player"
            + (f" with {used_weapon}." if used_weapon else "."),
        )

        for npc_id in location.npcs:
            witness = game.world.npcs.get(npc_id)
            if (
                witness
                and witness.id != attacker_npc.id
                and witness.hp > 0
            ):
                _record_npc_memory(
                    witness,
                    f"{attacker_npc.name} attacked the player.",
                )

        data: dict[str, Any] = {
            "attacker": attacker_npc.id,
            "target": "player",
            "weapon": used_weapon,
            "damage": damage,
            "target_hp": game.player.hp,
            "target_max_hp": game.player.max_hp,
            "target_dead": is_dead,
        }

        if is_dead:
            data["game_over"] = True

        return ActionResult(
            True,
            (
                f"{attacker_npc.name} attacks you"
                + (f" with {used_weapon}" if used_weapon else "")
                + f" for {damage} damage."
                + (
                    " You are dead."
                    if is_dead
                    else ""
                )
            ),
            data,
        )

    return ActionResult(
        False,
        "Attack could not be resolved.",
        {"attacker": attacker, "target": target,
         "reason": "unresolved"},
    )


def _time_to_minutes(time_string: str) -> int:
    try:
        hours, minutes = time_string.split(":")
        return int(hours) * 60 + int(minutes)
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------
# QUESTS
# ---------------------------------------------------------

_VALID_QUEST_OBJECTIVE_TYPES = frozenset({
    "kill", "find", "talk", "visit",
})


def _find_quest(game: GameState, quest_id: str) -> Quest | None:
    """Return a quest by id, or None."""
    return game.quests.get(quest_id)


def _check_quest_progress(
    game: GameState,
    objective_type: str,
    target: str,
) -> list[dict]:
    """Check all active quests for matching objectives and advance them.

    Returns a list of dicts describing progress events for the result data.
    """

    events = []

    for quest in game.quests.values():
        if quest.state != "active":
            continue

        for obj in quest.objectives:
            if obj.completed:
                continue

            if obj.type != objective_type:
                continue

            target_lower = obj.target.lower().strip().replace("_", " ")
            match_lower = target.lower().strip().replace("_", " ")

            matched = (
                target_lower == match_lower
                or match_lower in target_lower
                or target_lower in match_lower
            )

            if not matched:
                continue

            old_current = obj.current
            obj.current = min(obj.current + 1, obj.required)

            events.append({
                "quest_id": quest.id,
                "objective_id": obj.id,
                "type": objective_type,
                "target": target,
                "old_current": old_current,
                "new_current": obj.current,
            })

        _check_and_complete_quest(game, quest)

    return events


def _check_and_complete_quest(
    game: GameState,
    quest: Quest,
) -> bool:
    """Check if a quest's objectives are all complete. If so, complete it.

    Returns True if the quest was completed.
    """

    if quest.state != "active":
        return False

    if not all(obj.completed for obj in quest.objectives):
        return False

    quest.state = "completed"

    # Apply rewards
    _apply_quest_rewards(game, quest)

    # Record memory on the quest giver
    giver = game.world.npcs.get(quest.giver)
    if giver is not None:
        _record_npc_memory(
            giver,
            f"The player completed the quest: {quest.title}.",
        )

    return True


def _apply_quest_rewards(
    game: GameState,
    quest: Quest,
) -> None:
    """Apply quest rewards exactly once. Called on quest completion."""

    rewards = quest.rewards

    # Item rewards
    items = rewards.get("items", [])
    for item in items:
        if isinstance(item, str) and item:
            game.player.inventory.append(item)

    # Relationship rewards
    relationships = rewards.get("relationships", {})
    for npc_id, delta in relationships.items():
        if not isinstance(delta, (int, float)):
            continue
        npc = game.world.npcs.get(npc_id)
        if npc is not None:
            _adjust_relationship(npc, game.player.name, int(delta))
            _adjust_relationship(npc, npc.name, 0)  # no-op on self

    # XP rewards
    xp = rewards.get("xp", 0)
    if isinstance(xp, (int, float)) and xp > 0:
        _award_xp(game, int(xp), "quest_completion")


def _fail_quest(game: GameState, quest: Quest) -> None:
    """Mark a quest as failed. Called when the quest giver dies."""

    if quest.state not in ("offered", "active"):
        return

    quest.state = "failed"


def offer_quest(
    game: GameState,
    actor: str,
    quest_id: str,
    title: str,
    description: str,
    objectives: list,
    rewards: dict | None = None,
) -> ActionResult:
    """NPC offers a quest to the player. Python validates everything."""

    # Validate actor
    actor_npc = _find_any_npc(game, actor)
    if actor_npc is None:
        return ActionResult(
            False,
            f"NPC '{actor}' does not exist.",
            {"reason": "actor_not_found"},
        )

    if actor_npc.hp <= 0:
        return ActionResult(
            False,
            f"{actor_npc.name} is dead.",
            {"reason": "actor_dead"},
        )

    location = game.current_location()
    if location is None:
        return ActionResult(
            False,
            "You are nowhere.",
            {"reason": "no_location"},
        )

    if actor_npc.id not in location.npcs:
        return ActionResult(
            False,
            f"{actor_npc.name} is not here.",
            {"reason": "actor_not_here"},
        )

    # Validate quest_id
    if not quest_id or not isinstance(quest_id, str):
        return ActionResult(
            False,
            "Quest ID must be a non-empty string.",
            {"reason": "invalid_quest_id"},
        )

    quest_id = quest_id.strip()
    if quest_id in game.quests:
        return ActionResult(
            False,
            f"Quest '{quest_id}' already exists.",
            {"reason": "duplicate_quest_id"},
        )

    # Validate title and description
    if not title or not isinstance(title, str):
        return ActionResult(
            False,
            "Quest title must be a non-empty string.",
            {"reason": "invalid_title"},
        )

    if not description or not isinstance(description, str):
        return ActionResult(
            False,
            "Quest description must be a non-empty string.",
            {"reason": "invalid_description"},
        )

    # Validate objectives
    if not objectives or not isinstance(objectives, list):
        return ActionResult(
            False,
            "Quest must have at least one objective.",
            {"reason": "no_objectives"},
        )

    parsed_objectives = []
    seen_obj_ids = set()

    for i, obj_raw in enumerate(objectives):
        if not isinstance(obj_raw, dict):
            return ActionResult(
                False,
                f"Objective {i} must be a dict.",
                {"reason": "invalid_objective", "index": i},
            )

        obj_id = obj_raw.get("id", "")
        obj_type = obj_raw.get("type", "")
        obj_target = obj_raw.get("target", "")
        obj_desc = obj_raw.get("description", "")
        obj_required = obj_raw.get("required", 1)

        if not obj_id or not isinstance(obj_id, str):
            return ActionResult(
                False,
                f"Objective {i} must have a non-empty string id.",
                {"reason": "invalid_objective_id", "index": i},
            )

        obj_id = obj_id.strip()
        if obj_id in seen_obj_ids:
            return ActionResult(
                False,
                f"Duplicate objective id '{obj_id}' in quest.",
                {"reason": "duplicate_objective_id", "index": i},
            )
        seen_obj_ids.add(obj_id)

        if obj_type not in _VALID_QUEST_OBJECTIVE_TYPES:
            return ActionResult(
                False,
                f"Invalid objective type '{obj_type}'. "
                f"Valid types: {sorted(_VALID_QUEST_OBJECTIVE_TYPES)}.",
                {"reason": "invalid_objective_type", "index": i},
            )

        if not obj_target or not isinstance(obj_target, str):
            return ActionResult(
                False,
                f"Objective {i} must have a non-empty string target.",
                {"reason": "invalid_objective_target", "index": i},
            )

        if not obj_desc or not isinstance(obj_desc, str):
            return ActionResult(
                False,
                f"Objective {i} must have a non-empty string description.",
                {"reason": "invalid_objective_description", "index": i},
            )

        if not isinstance(obj_required, (int, float)) or obj_required < 1:
            return ActionResult(
                False,
                f"Objective {i} required must be >= 1.",
                {"reason": "invalid_objective_required", "index": i},
            )

        obj_required = int(obj_required)

        # Validate target exists
        obj_target_stripped = obj_target.strip()

        if obj_type == "kill":
            target_npc = _find_any_npc(game, obj_target_stripped)
            if target_npc is None:
                return ActionResult(
                    False,
                    f"Kill target '{obj_target_stripped}' does not exist.",
                    {"reason": "invalid_kill_target", "index": i},
                )
            # Use canonical NPC id as target
            obj_target_stripped = target_npc.id

        elif obj_type == "talk":
            target_npc = _find_any_npc(game, obj_target_stripped)
            if target_npc is None:
                return ActionResult(
                    False,
                    f"Talk target '{obj_target_stripped}' does not exist.",
                    {"reason": "invalid_talk_target", "index": i},
                )
            obj_target_stripped = target_npc.id

        elif obj_type == "visit":
            target_loc = game.world.locations.get(obj_target_stripped)
            if target_loc is None:
                # Try fuzzy match
                found = False
                for loc_id, loc in game.world.locations.items():
                    if (
                        loc_id.lower() == obj_target_stripped.lower()
                        or loc.name.lower() == obj_target_stripped.lower()
                        or obj_target_stripped.lower() in loc.name.lower()
                    ):
                        obj_target_stripped = loc_id
                        found = True
                        break
                if not found:
                    return ActionResult(
                        False,
                        f"Visit target '{obj_target_stripped}' "
                        f"does not exist.",
                        {"reason": "invalid_visit_target", "index": i},
                    )

        elif obj_type == "find":
            # Find targets are item names. We allow any string since items
            # are bare strings and may not exist yet in the world.
            pass

        parsed_objectives.append(QuestObjective(
            id=obj_id,
            type=obj_type,
            target=obj_target_stripped,
            description=obj_desc,
            required=obj_required,
            current=0,
        ))

    # Validate rewards
    if rewards is None:
        rewards = {}

    if not isinstance(rewards, dict):
        return ActionResult(
            False,
            "Rewards must be a dict.",
            {"reason": "invalid_rewards"},
        )

    reward_items = rewards.get("items", [])
    if not isinstance(reward_items, list):
        return ActionResult(
            False,
            "Reward items must be a list.",
            {"reason": "invalid_reward_items"},
        )

    for item in reward_items:
        if not isinstance(item, str) or not item:
            return ActionResult(
                False,
                "Each reward item must be a non-empty string.",
                {"reason": "invalid_reward_item"},
            )

    reward_rels = rewards.get("relationships", {})
    if not isinstance(reward_rels, dict):
        return ActionResult(
            False,
            "Reward relationships must be a dict.",
            {"reason": "invalid_reward_relationships"},
        )

    for npc_id, delta in reward_rels.items():
        if not isinstance(delta, (int, float)):
            return ActionResult(
                False,
                f"Relationship delta for '{npc_id}' must be a number.",
                {"reason": "invalid_relationship_delta"},
            )
        npc = game.world.npcs.get(npc_id)
        if npc is None:
            return ActionResult(
                False,
                f"Relationship target NPC '{npc_id}' does not exist.",
                {"reason": "invalid_relationship_target"},
            )

    # Create the quest
    quest = Quest(
        id=quest_id,
        title=title.strip(),
        description=description.strip(),
        giver=actor_npc.id,
        state="offered",
        objectives=parsed_objectives,
        rewards=rewards,
        offered_at=game.player.location,
        offered_time=game.world.time,
    )

    game.quests[quest_id] = quest

    # Record memory on the quest giver
    _record_npc_memory(
        actor_npc,
        f"The player was offered the quest: {quest.title}.",
    )

    return ActionResult(
        True,
        f"{actor_npc.name} offers you a quest: {quest.title}.",
        {
            "quest_id": quest_id,
            "quest_title": quest.title,
            "giver": actor_npc.id,
        },
    )


def accept_quest(
    game: GameState,
    quest_id: str,
) -> ActionResult:
    """Player accepts an offered quest."""

    quest = _find_quest(game, quest_id)
    if quest is None:
        return ActionResult(
            False,
            f"Quest '{quest_id}' does not exist.",
            {"reason": "quest_not_found"},
        )

    if quest.state != "offered":
        return ActionResult(
            False,
            f"Quest '{quest.title}' is not in offered state.",
            {"reason": "invalid_state", "state": quest.state},
        )

    quest.state = "active"

    giver = game.world.npcs.get(quest.giver)
    if giver is not None:
        _record_npc_memory(
            giver,
            f"The player accepted the quest: {quest.title}.",
        )

    return ActionResult(
        True,
        f"You accept the quest: {quest.title}.",
        {
            "quest_id": quest_id,
            "quest_title": quest.title,
        },
    )


def decline_quest(
    game: GameState,
    quest_id: str,
) -> ActionResult:
    """Player declines an offered quest. Quest is removed."""

    quest = _find_quest(game, quest_id)
    if quest is None:
        return ActionResult(
            False,
            f"Quest '{quest_id}' does not exist.",
            {"reason": "quest_not_found"},
        )

    if quest.state != "offered":
        return ActionResult(
            False,
            f"Quest '{quest.title}' is not in offered state.",
            {"reason": "invalid_state", "state": quest.state},
        )

    giver = game.world.npcs.get(quest.giver)
    if giver is not None:
        _record_npc_memory(
            giver,
            f"The player declined the quest: {quest.title}.",
        )

    del game.quests[quest_id]

    return ActionResult(
        True,
        f"You decline the quest: {quest.title}.",
        {
            "quest_id": quest_id,
            "quest_title": quest.title,
        },
    )


def abandon_quest(
    game: GameState,
    quest_id: str,
) -> ActionResult:
    """Player abandons an active quest."""

    quest = _find_quest(game, quest_id)
    if quest is None:
        return ActionResult(
            False,
            f"Quest '{quest_id}' does not exist.",
            {"reason": "quest_not_found"},
        )

    if quest.state != "active":
        return ActionResult(
            False,
            f"Quest '{quest.title}' is not active.",
            {"reason": "invalid_state", "state": quest.state},
        )

    quest.state = "abandoned"

    giver = game.world.npcs.get(quest.giver)
    if giver is not None:
        _record_npc_memory(
            giver,
            f"The player abandoned the quest: {quest.title}.",
        )

    return ActionResult(
        True,
        f"You abandon the quest: {quest.title}.",
        {
            "quest_id": quest_id,
            "quest_title": quest.title,
        },
    )
