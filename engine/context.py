from .state import GameState


def build_game_context(game: GameState) -> str:
    """
    Convert the current game state into a compact context
    that can be given to the AI.
    """

    player = game.player
    world = game.world
    location = game.current_location()

    lines = [
        "=== WORLD STATE ===",
        f"World: {world.name}",
        f"Genre: {world.genre}",
        f"Day: {world.day}",
        f"Time: {world.time}",
        f"Weather: {world.weather}",
        "",
        "=== PLAYER ===",
        f"Name: {player.name}",
        f"HP: {player.hp}/{player.max_hp}",
        f"Location: {player.location}",
        "Inventory:",
    ]

    if player.inventory:
        for item in player.inventory:
            lines.append(f"- {item}")
    else:
        lines.append("- Empty")

    if location:
        lines.extend([
            "",
            "=== CURRENT LOCATION ===",
            f"Name: {location.name}",
            f"Description: {location.description}",
        ])

        if location.exits:
            lines.append("Exits:")

            for direction, destination in location.exits.items():
                destination_location = world.locations.get(destination)

                if destination_location:
                    lines.append(
                        f"- {direction} → {destination_location.name}"
                    )
                else:
                    lines.append(
                        f"- {direction} → Unknown"
                    )

        if location.items:
            lines.append("Items:")

            for item in location.items:
                lines.append(f"- {item}")

        if location.npcs:
            lines.append("NPCs:")
            lines.append("  (Note: Each NPC only knows what is listed in its own Knowledge section. Global world-state info above is NOT automatically known by any NPC. Beliefs are the NPC's subjective view and may be incorrect; game state remains authoritative. A listed Belief reflects the NPC's current opinion and should be expressed, not contradicted. Goals are what the NPC wants; they never change game state. Relationships are the NPC's subjective attitude toward others; they do not change game state. Routine is a descriptive list of the NPC's habits and hobbies; the Schedule maps hours to the location where Python moves the NPC. NPCs listed together at a location are present and may speak to one another.)")

            for npc_id in location.npcs:
                npc = world.npcs.get(npc_id)

                if npc:
                    lines.append(
                        f"- {npc.name}"
                    )
                    lines.append(
                        f"  id: {npc.id}"
                    )
                    lines.append(
                        f"  Description: {npc.description}"
                    )

                    if npc.current_activity:
                        lines.append(
                            "  Current Activity: "
                            f"{npc.current_activity} "
                            "(authoritative current state)"
                        )

                    if npc.current_activity_object:
                        activity_obj = world.interactables.get(
                            npc.current_activity_object
                        )

                        if activity_obj:
                            object_label = activity_obj.name
                        else:
                            object_label = npc.current_activity_object

                        lines.append(
                            f"  Activity Object: {object_label} "
                            f"(id: {npc.current_activity_object})"
                        )

                    lines.append(
                        f"  Disposition: {npc.disposition}"
                    )

                    if npc.personality:
                        lines.append(
                            "  Personality:"
                        )

                        for trait in npc.personality:
                            lines.append(
                                f"    - {trait}"
                            )

                    if npc.memory:
                        lines.append(
                            "  Memory: (recorded events - authoritative)"
                        )

                        for entry in npc.memory:
                            lines.append(
                                f"    - {entry}"
                            )

                    if npc.knowledge:
                        lines.append(
                            "  Knowledge:"
                        )

                        for fact in npc.knowledge:
                            lines.append(
                                f"    - {fact}"
                            )

                    if npc.beliefs:
                        lines.append(
                            "  Beliefs:"
                        )

                        for belief in npc.beliefs:
                            lines.append(
                                f"    - {belief}"
                            )

                    if npc.goals:
                        lines.append(
                            "  Goals:"
                        )

                        for goal in npc.goals:
                            lines.append(
                                f"    - {goal}"
                            )

                    if npc.relationships:
                        lines.append(
                            "  Relationships:"
                        )

                        for target, score in npc.relationships.items():
                            lines.append(
                                f"    - {target}: {score}"
                            )

                    if npc.routine:
                        lines.append(
                            "  Routine: (descriptive habits - "
                            "NOT a record of specific events or movements)"
                        )

                        for activity in npc.routine:
                            lines.append(
                                f"    - {activity}"
                            )

                    if npc.schedule:
                        lines.append(
                            "  Schedule: (hour -> "
                            "where Python moves the NPC)"
                        )

                        for hour, target_id in sorted(
                            npc.schedule.items()
                        ):
                            target_location = world.locations.get(
                                target_id
                            )

                            if target_location:
                                lines.append(
                                    f"    - {hour}:00 → "
                                    f"{target_location.name}"
                                )
                            else:
                                lines.append(
                                    f"    - {hour}:00 → {target_id}"
                                )
                else:
                    lines.append(
                        f"- Unknown NPC ({npc_id})"
                    )

        # -----------------------------------------------------
        # INTERACTABLE OBJECTS
        # -----------------------------------------------------

        if location.interactables:
            lines.append("Interactable Objects:")
            lines.append("  (IMPORTANT: The CURRENT STATE field is authoritative. Object names may reflect their original/default state and should not be used to infer current state.)")

            for interactable_id in location.interactables:
                obj = world.interactables.get(interactable_id)

                if obj:
                    lines.append(
                        f"- {obj.name}"
                    )
                    lines.append(
                        f"  id: {obj.id}"
                    )
                    lines.append(
                        f"  CURRENT STATE: {obj.state}"
                    )
                    lines.append(
                        f"  Description: {obj.description}"
                    )

                    if obj.discovered:
                        lines.append(
                            "  Discovered: yes"
                        )
                    else:
                        lines.append(
                            "  Discovered: no"
                        )

                    if obj.used:
                        lines.append(
                            "  Used: yes"
                        )
                    else:
                        lines.append(
                            "  Used: no"
                        )

                    used_by = []

                    for npc_id in location.npcs:
                        npc = world.npcs.get(npc_id)

                        if (
                            npc
                            and npc.current_activity_object == obj.id
                        ):
                            used_by.append(npc.name)

                    if used_by:
                        lines.append(
                            f"  Used by: {', '.join(used_by)}"
                        )

                else:
                    lines.append(
                        f"- Unknown interactable ({interactable_id})"
                    )

    return "\n".join(lines)
