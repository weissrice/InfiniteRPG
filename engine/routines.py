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
    """Set each NPC's current activity from its activity data.

    The current hour drives the activity table. This is fully
    deterministic and data-driven; no AI decision-making. Activity
    updates apply even when the NPC does not change location.

    Returns a list of human-readable activity change descriptions.
    """

    hour = _current_hour(game)

    changes: List[str] = []

    for npc in game.world.npcs.values():
        activity = npc.activity_by_time.get(hour)

        if activity is None:
            continue

        if activity == npc.current_activity:
            continue

        npc.current_activity = activity

        changes.append(
            f"{npc.name} is now {activity}."
        )

    return changes
