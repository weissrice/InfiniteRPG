import builtins
import json
import os
from pathlib import Path

from engine.world import create_new_game
from engine.context import build_game_context
from engine.game import SYSTEM_PROMPT, GameEngine
from engine.actions import (
    wait,
    move_player,
    npc_interact,
    _record_npc_memory,
)
from engine.save import save_game, load_game


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    if detail and not condition:
        print(f"    detail: {detail}")
    return condition


def kitchen_evening():
    game = create_new_game()
    wait(game, 360)
    move_player(game, "kitchen")
    return game


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 0. Prompt - NPC SOCIAL INTERACTION RULES ===")
results.append(check(
    "NPC SOCIAL INTERACTION RULES section present",
    "NPC SOCIAL INTERACTION RULES:" in system,
))
results.append(check(
    "Three interaction directions declared",
    "one of exactly three directions" in normalized,
))
results.append(check(
    "NPC -> NPC format example present",
    '{"type": "interact", "actor": "old_man", "target": "sarah",'
    in normalized
    and '"topic": "the evening meal"}' in normalized,
))
results.append(check(
    "Actor must never target itself",
    "must never target itself" in normalized,
))
results.append(check(
    "Both NPCs must be present at the current location",
    "Python requires both NPCs to be present at the player's current"
    in normalized,
))
results.append(check(
    "No lock / busy / session state",
    "no lock, busy flag, or session state" in normalized,
))
results.append(check(
    "EACH NPC speaks from its OWN state",
    "each npc in its own supplied state" in normalized.lower(),
))
results.append(check(
    "Conversation changes nothing; Python records compact memory",
    "a conversation changes nothing" in normalized.lower()
    and "records a compact memory" in normalized,
))
results.append(check(
    "No autonomous NPC conversations",
    "they are not autonomous" in normalized.lower(),
))
results.append(check(
    "Direction rule: Player -> NPC uses NO actor (preserved)",
    "with NO \"actor\" field and \"target\" set to that NPC"
    in normalized,
))
results.append(check(
    "Direction rule: NPC -> Player example has actor (preserved)",
    '"type": "interact", "actor": "old_man", "target": "Traveler",'
    in normalized,
))
results.append(check(
    "NPCs may use only interact and interact_object (preserved)",
    'may use "interact" and "interact_object"' in normalized,
))

print("\n=== 1. Seed data - Sarah, the second persistent NPC ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
results.append(check(
    "Sarah exists in the world",
    sarah is not None,
))
results.append(check(
    "Sarah listed at the old house at start",
    "sarah" in game.world.locations["old_wooden_house"].npcs,
))
results.append(check(
    "Sarah's schedule puts her in the kitchen at 18:00",
    sarah.schedule.get("18") == "kitchen",
))
results.append(check(
    "Old Man -> Sarah static relationship seeded",
    old_man.relationships.get("Sarah") == 3,
))
results.append(check(
    "Sarah -> Old Man static relationship seeded",
    sarah.relationships.get("Old Man") == 10,
))
results.append(check(
    "Old Man -> Traveler relationship unchanged",
    old_man.relationships.get("Traveler") == 10,
))
results.append(check(
    "Sarah has no activity object binding",
    sarah.current_activity_object == ""
    and sarah.activity_objects_by_time == {},
))

print("\n=== 2. Co-location at 18:00 in the Kitchen ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
results.append(check(
    "Time advanced to 18:00",
    game.world.time == "18:00",
))
results.append(check(
    "Old Man moved to the kitchen",
    old_man.location == "kitchen",
))
results.append(check(
    "Sarah moved to the kitchen",
    sarah.location == "kitchen",
))
results.append(check(
    "Both NPCs listed at the current location",
    "old_man" in game.current_location().npcs
    and "sarah" in game.current_location().npcs,
))
results.append(check(
    "Old Man bound to the Pot at 18:00",
    old_man.current_activity_object == "kitchen_stew_pot",
))

print("\n=== 3. npc_interact - valid NPC -> NPC initiation ===")
res = npc_interact(game, "old_man", "sarah", "the evening meal")
results.append(check(
    "Dialogue succeeds with actor data",
    res.success is True and res.data["actor"] == "old_man",
))
results.append(check(
    "Data carries the target NPC name",
    res.data["target"] == "Sarah",
))
results.append(check(
    "Initiation memory on the actor",
    "Old Man spoke to Sarah about the evening meal." in old_man.memory,
))
results.append(check(
    "Reception memory on the target",
    "Old Man spoke with Sarah about the evening meal." in sarah.memory,
))
results.append(check(
    "No player misremembering on the NPC target",
    not any("player" in m for m in sarah.memory),
))

print("\n=== 4. Symmetric direction: Sarah -> Old Man ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(game, "sarah", "old_man", "the house")
results.append(check(
    "Reverse initiation succeeds",
    res.success is True and res.data["target"] == "Old Man",
))
results.append(check(
    "Sarah initiation memory",
    "Sarah spoke to Old Man about the house." in sarah.memory,
))
results.append(check(
    "Old Man reception memory",
    "Sarah spoke with Old Man about the house." in old_man.memory,
))

print("\n=== 5. Empty topic ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(game, "old_man", "sarah")
results.append(check(
    "Empty-topic NPC -> NPC succeeds",
    res.success is True,
))
results.append(check(
    "Generic actor memory",
    "Old Man spoke to Sarah." in old_man.memory,
))
results.append(check(
    "Generic target memory",
    "Old Man spoke with Sarah." in sarah.memory,
))

print("\n=== 6. Rejections with zero mutation ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
before_mem_a = list(old_man.memory)
before_mem_b = list(sarah.memory)
before_rel_a = dict(old_man.relationships)
before_rel_b = dict(sarah.relationships)

res = npc_interact(game, "old_man", "old_man", "anything")
results.append(check(
    "Self-target rejected",
    res.success is False,
))
results.append(check(
    "Self-target message",
    "cannot talk to itself" in res.message,
))

res = npc_interact(game, "ghost", "sarah", "anything")
results.append(check(
    "Unknown actor rejected",
    res.success is False,
))
res = npc_interact(game, "old_man", "ghost", "anything")
results.append(check(
    "Unknown target rejected",
    res.success is False,
))
res = npc_interact(game, "old_man", "", "anything")
results.append(check(
    "Empty target rejected",
    res.success is False,
))
res = npc_interact(game, "Traveler", "sarah", "anything")
results.append(check(
    "Player name as actor rejected",
    res.success is False,
))
res = npc_interact(game, "sarah", "sarah", "anything")
results.append(check(
    "Sarah self-target rejected too",
    res.success is False,
))
results.append(check(
    "No memory written by any rejection",
    old_man.memory == before_mem_a and sarah.memory == before_mem_b,
))
results.append(check(
    "No relationships written by any rejection",
    old_man.relationships == before_rel_a
    and sarah.relationships == before_rel_b,
))

print("\n=== 7. Location gating for both participants ===")


def move_npc(game, npc_id, to_location):
    npc = game.world.npcs[npc_id]
    from_location = game.world.locations[npc.location]

    if npc.id in from_location.npcs:
        from_location.npcs.remove(npc.id)

    npc.location = to_location

    target_location = game.world.locations[to_location]

    if npc.id not in target_location.npcs:
        target_location.npcs.append(npc.id)


game = kitchen_evening()
move_npc(game, "old_man", "old_wooden_house")
res = npc_interact(game, "old_man", "sarah", "anything")
results.append(check(
    "Actor not at the current location rejected",
    res.success is False,
))

game = kitchen_evening()
move_npc(game, "sarah", "old_wooden_house")
res = npc_interact(game, "old_man", "sarah", "anything")
results.append(check(
    "Target not at the current location rejected",
    res.success is False,
))

print("\n=== 8. Non-relationship state never mutates on success ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
pot = game.world.interactables["kitchen_stew_pot"]


def non_relationship_snapshot(game):
    om = game.world.npcs["old_man"]
    sa = game.world.npcs["sarah"]
    p = game.world.interactables["kitchen_stew_pot"]
    return (
        tuple(om.beliefs),
        tuple(sa.beliefs),
        tuple(om.knowledge),
        tuple(sa.knowledge),
        tuple(om.goals),
        tuple(sa.goals),
        om.current_activity,
        sa.current_activity,
        om.current_activity_object,
        sa.current_activity_object,
        p.state,
        p.used,
        p.discovered,
        tuple(p.memory),
        game.world.time,
        om.location,
        sa.location,
    )


before = non_relationship_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "the meal")
after = non_relationship_snapshot(game)
results.append(check(
    "All non-relationship state identical after a successful conversation",
    before == after,
))
results.append(check(
    "Old Man -> Sarah relationship advanced by exactly +1",
    old_man.relationships.get("Sarah") == 4,
))
results.append(check(
    "Sarah -> Old Man relationship advanced by exactly +1",
    sarah.relationships.get("Old Man") == 11,
))
results.append(check(
    "relationship_update datum carried on success",
    res.data.get("relationship_update") == {
        "delta": 1,
        "target": "Sarah",
        "actor_score": 4,
        "target_score": 11,
    },
))

print("\n=== 9. Deduplication ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "old_man", "sarah", "the evening meal")
npc_interact(game, "old_man", "sarah", "the evening meal")
results.append(check(
    "Repeated conversation does not duplicate entries",
    old_man.memory.count("Old Man spoke to Sarah about the evening meal.") == 1
    and sarah.memory.count("Old Man spoke with Sarah about the evening meal.") == 1,
))
results.append(check(
    "Repeated conversation does not re-apply the relationship delta",
    old_man.relationships.get("Sarah") == 4
    and sarah.relationships.get("Old Man") == 11,
))

print("\n=== 10. 20-entry memory cap still enforced ===")
g2 = create_new_game()
om2 = g2.world.npcs["old_man"]
for i in range(25):
    _record_npc_memory(om2, f"entry {i}")
results.append(check(
    "Memory capped at 20",
    len(om2.memory) == 20,
))
results.append(check(
    "Newest entries kept, oldest dropped",
    "entry 24" in om2.memory and "entry 0" not in om2.memory,
))

print("\n=== 11. Engine dispatch of an NPC -> NPC action ===")


class ActionAI:
    def __init__(self, action):
        self.action = action

    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        return json.dumps({
            "narration": (
                'Old Man stirs the pot. "Sarah, mind the meal." '
                '"I always do," she replies.'
            ),
            "actions": [self.action],
        })

    def close(self):
        pass


def run(action, game):
    engine = GameEngine()
    engine.game = game
    engine.ai = ActionAI(action)
    old = builtins.input
    builtins.input = lambda _="": ""
    try:
        return engine.process_input("test")
    finally:
        builtins.input = old


game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
result = run({
    "type": "interact",
    "actor": "old_man",
    "target": "sarah",
    "topic": "the evening meal",
}, game=game)
results.append(check(
    "NPC -> NPC executes through the engine",
    result["success"] is True
    and result["actions"][0]["success"] is True
    and result["actions"][0]["data"]["target"] == "Sarah",
))
results.append(check(
    "Engine path records both memories",
    "Old Man spoke to Sarah about the evening meal." in old_man.memory
    and "Old Man spoke with Sarah about the evening meal." in sarah.memory,
))
results.append(check(
    "No 'told the player' summary for an NPC-targeted exchange",
    not any("told the player" in m for m in old_man.memory + sarah.memory),
))

game = kitchen_evening()
old_man = game.world.npcs["old_man"]
before_engine_self = list(old_man.memory)
result = run({
    "type": "interact",
    "actor": "old_man",
    "target": "old_man",
    "topic": "anything",
}, game=game)
results.append(check(
    "Engine rejects self-target before any state change",
    result["actions"][0]["success"] is False,
))
results.append(check(
    "No new memory recorded for self-target through the engine",
    game.world.npcs["old_man"].memory == before_engine_self,
))

print("\n=== 12. Player -> NPC interaction is unaffected ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
result = run({
    "type": "interact",
    "target": "old_man",
    "topic": "the old door",
}, game=game)
results.append(check(
    "Player interact (no actor) still succeeds",
    result["success"] is True and result["actions"][0]["success"] is True,
))
results.append(check(
    "Player question memory unchanged",
    "The player asked Old Man about the old door." in old_man.memory,
))

print("\n=== 13. Save/load preserves NPC -> NPC memory ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "sarah", "old_man", "the house")
path = Path("test_social_save.json")
try:
    save_game(game, path=path)
    loaded = load_game(path=path)
    loaded_old_man = loaded.world.npcs["old_man"]
    loaded_sarah = loaded.world.npcs["sarah"]
    results.append(check(
        "Sarah persists on load",
        loaded_sarah.id == "sarah",
    ))
    results.append(check(
        "Actor memory persists",
        "Sarah spoke to Old Man about the house." in loaded_sarah.memory,
    ))
    results.append(check(
        "Target memory persists",
        "Sarah spoke with Old Man about the house." in loaded_old_man.memory,
    ))
    results.append(check(
        "Relationship seeds persist with evolution applied",
        loaded_old_man.relationships.get("Sarah") == 4
        and loaded_sarah.relationships.get("Old Man") == 11,
    ))
finally:
    if path.exists():
        os.remove(path)

print("\n=== 14. Context rendering ===")
game = kitchen_evening()
ctx = build_game_context(game)
results.append(check(
    "Sarah block renders under the NPC list",
    "- Sarah" in ctx and "id: sarah" in ctx,
))
results.append(check(
    "NPC note includes the co-location sentence",
    "NPCs listed together at a location are present and may speak to one another"
    in ctx,
))
results.append(check(
    "Relationships render for both directions",
    "Sarah: 3" in ctx and "Old Man: 10" in ctx,
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")