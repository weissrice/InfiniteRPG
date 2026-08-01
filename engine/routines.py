from typing import List

from .state import GameState


MAX_NPC_ROUTINE_MEMORY = 20


def _current_hour(game: GameState) -> str:
    """Return the current hour as a zero-padded two-digit string."""

    try:
        hours, _ = game.world.time.split(":")
        return f"{int(hours):02d}"
    except (ValueError, TypeError):
        return "00"


def _record_routine_memory(npc, entry: str) -> None:
    """Record a compact, deduplicated memory entry on an NPC."""

    if entry not in npc.memory:
        npc.memory.append(entry)

    if len(npc.memory) > MAX_NPC_ROUTINE_MEMORY:
        del npc.memory[:-MAX_NPC_ROUTINE_MEMORY]


def advance_npc_routines(game: GameState) -> List[str]:
    """Evaluate NPC schedules against the current time.

    For each NPC with a schedule, if the schedule maps the current hour
    to a different existing location, Python moves the NPC there. This
    is fully deterministic and data-driven; no AI decision-making.

    Returns a list of human-readable change descriptions.
    """

    hour = _current_hour(game)

    changes: List[str] = []

    for npc in game.world.npcs.values():
        target_id = npc.schedule.get(hour)

        if target_id is None:
            continue

        if target_id == npc.location:
            continue

        target_location = game.world.locations.get(target_id)

        if target_location is None:
            continue

        current_location = game.world.locations.get(npc.location)

        if current_location is not None:
            if npc.id in current_location.npcs:
                current_location.npcs.remove(npc.id)

        npc.location = target_id

        if npc.id not in target_location.npcs:
            target_location.npcs.append(npc.id)

        _record_routine_memory(
            npc,
            f"{npc.name} went to {target_location.name}.",
        )

        changes.append(
            f"{npc.name} moved to {target_location.name}."
        )

    return changes


def update_npc_activities(game: GameState) -> List[str]:
    """Set each NPC's current activity and activity object.

    The current hour drives both tables. This is fully deterministic
    and data-driven; no AI decision-making. Activity updates apply even
    when the NPC does not change location.

    The activity object binding is validated by Python: it must exist in
    the world and be located where the NPC currently is. A valid binding
    change records a memory-only interaction event on the NPC and the
    object. Invalid or missing bindings are cleared; object state,
    flags, items, doors, and locations are never changed.

    Returns a list of human-readable activity change descriptions.
    """

    hour = _current_hour(game)

    changes: List[str] = []

    for npc in game.world.npcs.values():
        activity = npc.activity_by_time.get(hour)
        object_id = npc.activity_objects_by_time.get(hour)

        if activity is not None and activity != npc.current_activity:
            npc.current_activity = activity

            changes.append(
                f"{npc.name} is now {activity}."
            )

        valid_object = ""

        if object_id is not None:
            obj = game.world.interactables.get(object_id)

            if obj is not None and obj.location == npc.location:
                valid_object = object_id

        if valid_object != npc.current_activity_object:
            if valid_object:
                obj = game.world.interactables[valid_object]

                _record_routine_memory(
                    npc,
                    f"{npc.name} used the {obj.name}.",
                )

                entry = f"{npc.name} used this."

                if entry not in obj.memory:
                    obj.memory.append(entry)

            npc.current_activity_object = valid_object

    return changes
