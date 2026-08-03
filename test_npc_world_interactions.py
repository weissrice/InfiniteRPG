import builtins
import json
import os
from pathlib import Path

from engine.world import create_new_game
from engine.context import build_game_context
from engine.game import SYSTEM_PROMPT, GameEngine
from engine.actions import wait, move_player, npc_interact_object
from engine.state import Interactable
from engine.save import save_game, load_game


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 0. Prompt contains NPC WORLD INTERACTION RULES ===")
results.append(check(
    "NPC WORLD INTERACTION RULES section present",
    "NPC WORLD INTERACTION RULES:" in system,
))
results.append(check(
    "AI proposes, Python validates and executes",
    "Python validates and executes it" in normalized,
))
results.append(check(
    "interact_object format example present",
    '{"type": "interact_object", "actor": "old_man", '
    '"target": "kitchen_stew_pot"}' in normalized,
))
results.append(check(
    "Strict validation: actor must be a valid NPC",
    "the actor must be a valid NPC" in normalized,
))
results.append(check(
    "Strict validation: NPC must be at the current location",
    "the NPC must be at the current location" in normalized,
))
results.append(check(
    "Strict validation: target must exist at that location",
    "the target must exist at that location" in normalized,
))
results.append(check(
    "Strict validation: target must equal the Activity Object",
    'the target must equal the NPC\'s "Activity Object"' in normalized,
))
results.append(check(
    "No Activity Object means no interact_object",
    "cannot use interact_object" in normalized,
))
results.append(check(
    "Effect is memory-only",
    "memory-only" in normalized,
))
results.append(check(
    "No object state/flag mutation",
    "never change an object's state" in normalized,
))
results.append(check(
    "NPC ACTION RULES permit interact_object",
    'may use "interact", "interact_object", and "attack"' in normalized
    and "interact_object" in system,
))
results.append(check(
    "No copyable denial phrasing in prompt",
    "was not using" not in normalized
    and "didn't use" not in normalized,
))

print("\n=== 0b. Repro: activity object carried in the real prompt ===")
captured = {}


class MockAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        captured["system"] = system
        captured["prompt"] = prompt
        return json.dumps({
            "narration": (
                "The Old Man stirs the pot. \"Preparing the evening "
                "meal, as you can see.\""
            ),
            "actions": [{
                "type": "interact",
                "target": "old_man",
                "topic": "what are you doing with the stew pot?",
            }],
        })

    def close(self):
        pass


engine = GameEngine()
engine.game = create_new_game()
wait(engine.game, 360)
move_player(engine.game, "kitchen")
engine.ai = MockAI()
old_input = builtins.input
builtins.input = lambda _="": ""
try:
    engine.process_input("ask old man: what are you doing with the stew pot?")
finally:
    builtins.input = old_input

results.append(check(
    "Activity Object present in repro prompt",
    "Activity Object: Stew Pot (id: kitchen_stew_pot)"
    in captured["prompt"],
))
results.append(check(
    "Used by line present in repro prompt",
    "Used by: Old Man" in captured["prompt"],
))
results.append(check(
    "NPC WORLD INTERACTION RULES carried in system prompt for repro",
    "NPC WORLD INTERACTION RULES:" in captured["system"]
    and "cannot use interact_object" in " ".join(captured["system"].split()),
))

print("\n=== 1. Seed data present ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
pot = game.world.interactables["kitchen_stew_pot"]
results.append(check(
    "Stew Pot exists at the kitchen",
    pot.location == "kitchen"
    and "kitchen_stew_pot" in game.world.locations["kitchen"].interactables,
))
results.append(check(
    "Stew Pot starts in default state with no memory",
    pot.state == "default"
    and pot.used is False
    and pot.discovered is False
    and pot.memory == [],
))
results.append(check(
    "Old Man binds the pot to the 18:00 activity",
    old_man.activity_objects_by_time.get("18") == "kitchen_stew_pot",
))
results.append(check(
    "No activity object bound at start (12:00)",
    old_man.current_activity_object == "",
))
results.append(check(
    "activity_by_time remains phrase-only",
    isinstance(old_man.activity_by_time.get("18"), str),
))

print("\n=== 2. Wait binds the activity object with a memory-only event ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
pot = game.world.interactables["kitchen_stew_pot"]
res = wait(game, 360)
results.append(check(
    "Time advances to 18:00",
    game.world.time == "18:00",
))
results.append(check(
    "Old Man moved to the kitchen",
    old_man.location == "kitchen",
))
results.append(check(
    "Activity object bound to the Stew Pot",
    old_man.current_activity_object == "kitchen_stew_pot",
))
results.append(check(
    "NPC memory records the interaction",
    "Old Man used the Stew Pot." in old_man.memory,
))
results.append(check(
    "Object memory records the interaction",
    "Old Man used this." in pot.memory,
))
results.append(check(
    "Object state and flags untouched",
    pot.state == "default"
    and pot.used is False
    and pot.discovered is False,
))
results.append(check(
    "Wait result still reports activity changes",
    "activity_changes" in res.data
    and "Old Man is now preparing the evening meal."
    in res.data["activity_changes"],
))

print("\n=== 3. Repeated wait within the same hour does not re-record ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
pot = game.world.interactables["kitchen_stew_pot"]
wait(game, 360)
wait(game, 1)
results.append(check(
    "Memory recorded exactly once",
    old_man.memory.count("Old Man used the Stew Pot.") == 1
    and pot.memory.count("Old Man used this.") == 1,
))

print("\n=== 4. Return trip clears the activity object ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
wait(game, 360)
wait(game, 180)
results.append(check(
    "Time advances to 21:00",
    game.world.time == "21:00",
))
results.append(check(
    "Activity object cleared on unbound hour",
    old_man.current_activity_object == "",
))
results.append(check(
    "Activity updated to the 21:00 entry",
    old_man.current_activity == "keeping watch over the house",
))
results.append(check(
    "Clearing records no new 'used' memory",
    old_man.memory.count("Old Man used the Stew Pot.") == 1,
))

print("\n=== 5. Invalid object binding is dropped, activity still updates ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
old_man.activity_objects_by_time["18"] = "missing_object"
wait(game, 360)
results.append(check(
    "Missing object binding dropped",
    old_man.current_activity_object == "",
))
results.append(check(
    "Activity still updates",
    old_man.current_activity == "preparing the evening meal",
))
game = create_new_game()
old_man = game.world.npcs["old_man"]
old_man.activity_objects_by_time["18"] = "locked_upstairs_door"
wait(game, 360)
results.append(check(
    "Misplaced object binding dropped",
    old_man.current_activity_object == "",
))

print("\n=== 6. npc_interact_object unit behavior ===")


def kitchen_evening():
    game = create_new_game()
    wait(game, 360)
    move_player(game, "kitchen")
    return game


game = kitchen_evening()
old_man = game.world.npcs["old_man"]
pot = game.world.interactables["kitchen_stew_pot"]
res = npc_interact_object(game, "old_man", "stew pot")
results.append(check(
    "Valid object interaction succeeds",
    res.success is True and res.data["target"] == "kitchen_stew_pot",
))
results.append(check(
    "Valid interaction records both memories",
    "Old Man used the Stew Pot." in old_man.memory
    and "Old Man used this." in pot.memory,
))
results.append(check(
    "Object still unmutated after success",
    pot.state == "default"
    and pot.used is False
    and pot.discovered is False,
))
res = npc_interact_object(game, "old_man", "ghost_pot")
results.append(check(
    "Nonexistent target rejected",
    res.success is False,
))
res = npc_interact_object(game, "ghost", "stew pot")
results.append(check(
    "Unknown actor rejected",
    res.success is False,
))
res = npc_interact_object(game, "old_man", "stew pot", )
game.player.location = "forest_edge"
res = npc_interact_object(game, "old_man", "stew pot")
results.append(check(
    "NPC not at current location rejected",
    res.success is False,
))
game = kitchen_evening()
game.world.interactables["kitchen_hearth"] = Interactable(
    id="kitchen_hearth",
    name="Hearth",
    description="A stone hearth.",
    location="kitchen",
)
game.world.locations["kitchen"].interactables.append("kitchen_hearth")
old_man = game.world.npcs["old_man"]
res = npc_interact_object(game, "old_man", "hearth")
results.append(check(
    "Target not equal to current activity object rejected",
    res.success is False,
))
results.append(check(
    "Illegal interaction records no memory",
    not any("Hearth" in m for m in old_man.memory),
))
res = npc_interact_object(game, "old_man", "")
results.append(check(
    "Empty target rejected",
    res.success is False,
))

print("\n=== 7. GameEngine dispatch of interact_object ===")


class ActionAI:
    def __init__(self, action):
        self.action = action

    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        return json.dumps({
            "narration": "The Old Man works at the pot.",
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
result = run({
    "type": "interact_object",
    "actor": "old_man",
    "target": "kitchen_stew_pot",
}, game=game)
results.append(check(
    "NPC interact_object executes through the engine",
    result["success"] is True
    and result["actions"][0]["success"] is True
    and result["actions"][0]["data"]["target"] == "kitchen_stew_pot",
))
results.append(check(
    "Engine path records the interaction memory",
    "Old Man used the Stew Pot." in old_man.memory,
))
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
before_memory = list(old_man.memory)
result = run({
    "type": "interact_object",
    "actor": "old_man",
    "target": "locked_upstairs_door",
}, game=game)
results.append(check(
    "Illegal target rejected by the engine",
    result["actions"][0]["success"] is False,
))
results.append(check(
    "No memory recorded for rejected engine action",
    old_man.memory == before_memory,
))
game = kitchen_evening()
result = run({
    "type": "move",
    "actor": "old_man",
    "destination": "forest_edge",
}, game=game)
results.append(check(
    "NPC still cannot move",
    result["actions"][0]["success"] is False,
))

print("\n=== 8. Save/load round-trip preserves activity object fields ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
path = Path("test_world_interaction_save.json")
try:
    save_game(game, path)
    loaded = load_game(path)
    loaded_old_man = loaded.world.npcs["old_man"]
    results.append(check(
        "current_activity_object preserved on load",
        loaded_old_man.current_activity_object == "kitchen_stew_pot",
    ))
    results.append(check(
        "activity_objects_by_time preserved on load",
        loaded_old_man.activity_objects_by_time
        == old_man.activity_objects_by_time,
    ))
finally:
    if path.exists():
        os.remove(path)

print("\n=== 9. Context rendering ===")
game = create_new_game()
ctx = build_game_context(game)
results.append(check(
    "No Activity Object line at start",
    "Activity Object:" not in ctx,
))
results.append(check(
    "No Used by line at start",
    "Used by:" not in ctx,
))
game = kitchen_evening()
ctx = build_game_context(game)
results.append(check(
    "Activity Object line present at 18:00",
    "Activity Object: Stew Pot (id: kitchen_stew_pot)" in ctx,
))
results.append(check(
    "Used by line present under the pot",
    "Used by: Old Man" in ctx,
))
results.append(check(
    "Stew Pot listed in Interactable Objects",
    "Interactable Objects:" in ctx and "Stew Pot" in ctx,
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
