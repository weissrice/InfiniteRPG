import builtins
import json
import os
from pathlib import Path

from engine.world import create_new_game
from engine.context import build_game_context
from engine.game import SYSTEM_PROMPT, GameEngine
from engine.save import save_game, load_game
from engine.actions import (
    use_item,
    open_interactable,
    move_player,
    interact,
)


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

game = create_new_game()
old_man = game.world.npcs["old_man"]

print("=== 1. Talk to the Old Man ===")
result = interact(game, "old man", "the upstairs")
results.append(check("Interact succeeds", result.success))
results.append(check("Memory recorded", len(old_man.memory) >= 1))

print("\n=== 2. Goals appear in context, separated from Beliefs ===")
context = build_game_context(game)
results.append(check("Goals section present", "Goals:" in context))
results.append(check("Goals come after Beliefs", context.index("Beliefs:") < context.index("Goals:")))
results.append(check(
    "Goal content present",
    "Keep the house safe." in context,
))
results.append(check(
    "Protect upstairs goal present",
    "Protect the upstairs area from unwanted visitors." in context,
))

print("\n=== 3/4/5/6. Goal question prompt carries grounding + goal ===")
captured = {}


class MockAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        if "Generate the single new location" in prompt:
            return (
                '{"name": "Master Bedroom", "id": "master_bedroom", '
                '"description": "A dusty old bedroom with a canopy bed and a boarded window.", '
                '"visual_type": "interior", "symbol": "bed", '
                '"items": [], "npcs": []}'
            )
        captured["system"] = system
        captured["prompt"] = prompt
        return json.dumps({
            "narration": (
                "The Old Man frowns. \"I'd rather nobody went upstairs. "
                "I like to keep that area to myself.\""
            ),
            "actions": [{
                "type": "interact",
                "target": "old_man",
                "topic": "what do you want to protect?",
            }],
        })

    def close(self):
        pass


engine = GameEngine()
engine.ai = MockAI()
old_input = builtins.input
builtins.input = lambda _="": ""
try:
    result = engine.process_input(
        "Ask the Old Man what he wants to protect."
    )
finally:
    builtins.input = old_input

results.append(check(
    "NPC GOAL RULES present in system prompt sent to AI",
    "NPC GOAL RULES:" in captured["system"],
))
results.append(check(
    "Goals shown as wants/desires",
    "describe what the NPC wants" in " ".join(captured["system"].split()),
))
results.append(check(
    "AI told not to present goal as objective fact",
    "NOT authoritative world facts" in captured["system"],
))
results.append(check(
    "AI told goals are not proof something happened",
    "Do NOT treat a goal as proof" in captured["system"],
))
results.append(check(
    "Goal content available to AI",
    "Protect the upstairs area from unwanted visitors." in captured["prompt"],
))
results.append(check(
    "Interact executes",
    result.get("success") is True,
))

print("\n=== 7-10. Distinctness of all NPC fields ===")
results.append(check("Knowledge distinct from Goals", context.index("Knowledge:") < context.index("Goals:")))
results.append(check("Beliefs distinct from Goals", context.index("Beliefs:") < context.index("Goals:")))
results.append(check("Memory intact", "Memory:" in context))
results.append(check("Personality intact", "Personality:" in context))
results.append(check(
    "Order: Personality < Memory < Knowledge < Beliefs < Goals",
    context.index("Personality:") < context.index("Memory:")
    and context.index("Memory:") < context.index("Knowledge:")
    and context.index("Knowledge:") < context.index("Beliefs:")
    and context.index("Beliefs:") < context.index("Goals:"),
))

print("\n=== 11. Save/load persists goals ===")
path = Path(os.environ.get("TEMP", ".")) / "test_goals_save.json"
save_game(game, path=path)
loaded = load_game(path=path)
lom = loaded.world.npcs["old_man"]
results.append(check("Goals persisted", lom.goals == old_man.goals))
results.append(check("Beliefs persisted", lom.beliefs == old_man.beliefs))
results.append(check("Knowledge persisted", lom.knowledge == old_man.knowledge))
results.append(check("Memory persisted", lom.memory == old_man.memory))
results.append(check("Personality persisted", lom.personality == old_man.personality))
results.append(check(
    "Goals in rebuilt context after load",
    "Keep the house safe." in build_game_context(loaded),
))
os.remove(path)

print("\n=== 12. Goals do not directly mutate game state ===")
g2 = create_new_game()
npc_before = g2.world.npcs["old_man"]
door = g2.world.interactables["locked_upstairs_door"]
player_items_before = list(g2.player.inventory)
player_loc_before = g2.player.location
interact(g2, "old man", "the upstairs")
results.append(check("No game state mutated by dialogue", (
    door.state == "locked"
    and g2.player.inventory == player_items_before
    and g2.player.location == player_loc_before
)))

print("\n=== 13. Item/door/location/movement mechanics ===")
g2.player.location = "upstairs"
r = use_item(g2, "Rusty Key", "door")
results.append(check("Unlock works", r.success and door.state == "unlocked"))
r = use_item(g2, "Torn Note", "door")
results.append(check("Wrong item protected", "Torn Note" in g2.player.inventory))
r = open_interactable(g2, "door", engine.ai)
results.append(check("Door opens + generates location", r.success and door.state == "open"))
r = move_player(g2, "upstairs", engine.ai)
results.append(check(
    "Movement into generated location works",
    r.success and g2.current_location().name == "Master Bedroom",
))

print("\n=== 14. Goal rules in system prompt ===")
results.append(check("NPC GOAL RULES present", "NPC GOAL RULES:" in SYSTEM_PROMPT))
results.append(check(
    "Goals in SUBJECTIVE hierarchy",
    "NPC goals" in SYSTEM_PROMPT,
))
results.append(check(
    "Goal never mutates game state",
    "A goal must never directly mutate game state" in SYSTEM_PROMPT,
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
