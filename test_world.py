from engine.world import create_new_game


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

game = create_new_game()

print("=== 1. World state ===")
results.append(check(
    "World name is set",
    len(game.world.name) > 0,
))
results.append(check(
    "Genre is set",
    len(game.world.genre) > 0,
))
results.append(check(
    "Has locations",
    len(game.world.locations) > 0,
))
results.append(check(
    "Has NPCs",
    len(game.world.npcs) > 0,
))
results.append(check(
    "Has interactables",
    len(game.world.interactables) > 0,
))

print("\n=== 2. Player state ===")
results.append(check(
    "Player name is set",
    len(game.player.name) > 0,
))
results.append(check(
    "Player has HP",
    game.player.hp > 0,
))
results.append(check(
    "Player has max_hp",
    game.player.max_hp >= game.player.hp,
))
results.append(check(
    "Player has a location",
    len(game.player.location) > 0,
))
results.append(check(
    "Player has inventory",
    isinstance(game.player.inventory, list),
))

print("\n=== 3. Current location ===")
location = game.current_location()
results.append(check(
    "Current location exists",
    location is not None,
))
if location:
    results.append(check(
        "Location has name",
        len(location.name) > 0,
    ))
    results.append(check(
        "Location has description",
        len(location.description) > 0,
    ))
    results.append(check(
        "Location has exits",
        isinstance(location.exits, dict),
    ))
    results.append(check(
        "Location has items",
        isinstance(location.items, list),
    ))
    results.append(check(
        "Location has npcs",
        isinstance(location.npcs, list),
    ))

print("\n=== 4. NPC state ===")
for npc_id, npc in game.world.npcs.items():
    results.append(check(
        f"NPC {npc_id} has name",
        len(npc.name) > 0,
    ))
    results.append(check(
        f"NPC {npc_id} has location",
        len(npc.location) > 0,
    ))
    results.append(check(
        f"NPC {npc_id} has personality",
        isinstance(npc.personality, list),
    ))
    results.append(check(
        f"NPC {npc_id} has knowledge",
        isinstance(npc.knowledge, list),
    ))
    results.append(check(
        f"NPC {npc_id} has beliefs",
        isinstance(npc.beliefs, list),
    ))
    results.append(check(
        f"NPC {npc_id} has goals",
        isinstance(npc.goals, list),
    ))
    results.append(check(
        f"NPC {npc_id} has relationships",
        isinstance(npc.relationships, dict),
    ))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
