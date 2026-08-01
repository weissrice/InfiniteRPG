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

print("\n=== 2-4. Relationships in context ===")
context = build_game_context(game)
results.append(check("Relationships section present", "Relationships:" in context))
results.append(check("Traveler relationship present", "- Traveler: 10" in context))
results.append(check(
    "Score is +10",
    game.world.npcs["old_man"].relationships.get("Traveler") == 10,
))
results.append(check(
    "Relationships come after Goals",
    context.index("Goals:") < context.index("Relationships:"),
))

print("\n=== 5/6/7. Relationship tone question prompt ===")
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
                "The Old Man smiles a little. \"You're welcome here, "
                "Traveler. You've been good to this house.\""
            ),
            "actions": [{
                "type": "interact",
                "target": "old_man",
                "topic": "are we friends?",
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
        "Ask the Old Man how he feels about you."
    )
finally:
    builtins.input = old_input

results.append(check(
    "NPC RELATIONSHIP RULES present in system prompt sent to AI",
    "NPC RELATIONSHIP RULES:" in captured["system"],
))
results.append(check(
    "Score meaning explained to AI",
    "-100 = extremely hostile, 0 = neutral, +100 = extremely friendly"
    in " ".join(captured["system"].split()),
))
results.append(check(
    "Score is authoritative for that NPC",
    "authoritative relationship state" in captured["system"],
))
results.append(check(
    "AI told relationship is subjective, not objective truth",
    "NOT objective facts about the other character" in captured["system"],
))
results.append(check(
    "Relationship available to AI",
    "- Traveler: 10" in captured["prompt"],
))
results.append(check(
    "Interact executes",
    result.get("success") is True,
))

print("\n=== 8-12. Distinctness of all NPC fields ===")
results.append(check("Goals distinct from Relationships", context.index("Goals:") < context.index("Relationships:")))
results.append(check("Beliefs distinct from Relationships", context.index("Beliefs:") < context.index("Relationships:")))
results.append(check("Knowledge distinct from Relationships", context.index("Knowledge:") < context.index("Relationships:")))
results.append(check("Memory intact", "Memory:" in context))
results.append(check("Personality intact", "Personality:" in context))
results.append(check(
    "Order: Personality < Memory < Knowledge < Beliefs < Goals < Relationships",
    context.index("Personality:") < context.index("Memory:")
    and context.index("Memory:") < context.index("Knowledge:")
    and context.index("Knowledge:") < context.index("Beliefs:")
    and context.index("Beliefs:") < context.index("Goals:")
    and context.index("Goals:") < context.index("Relationships:"),
))

print("\n=== 13. Save/load persists relationships ===")
path = Path(os.environ.get("TEMP", ".")) / "test_relationships_save.json"
save_game(game, path=path)
loaded = load_game(path=path)
lom = loaded.world.npcs["old_man"]
results.append(check("Relationships persisted", lom.relationships == old_man.relationships))
results.append(check("Goals persisted", lom.goals == old_man.goals))
results.append(check("Beliefs persisted", lom.beliefs == old_man.beliefs))
results.append(check("Knowledge persisted", lom.knowledge == old_man.knowledge))
results.append(check("Memory persisted", lom.memory == old_man.memory))
results.append(check("Personality persisted", lom.personality == old_man.personality))
results.append(check(
    "Relationship in rebuilt context after load",
    "- Traveler: 10" in build_game_context(loaded),
))
os.remove(path)

print("\n=== 14. Dialogue does not automatically modify the score ===")
g2 = create_new_game()
score_before = g2.world.npcs["old_man"].relationships.get("Traveler")
interact(g2, "old man", "the upstairs")
results.append(check("Score unchanged after talk", g2.world.npcs["old_man"].relationships.get("Traveler") == score_before))

print("\n=== 15. Relationships do not directly mutate game state ===")
door = g2.world.interactables["locked_upstairs_door"]
player_items_before = list(g2.player.inventory)
player_loc_before = g2.player.location
interact(g2, "old man", "the upstairs")
results.append(check("No game state mutated", (
    door.state == "locked"
    and g2.player.inventory == player_items_before
    and g2.player.location == player_loc_before
)))

print("\n=== 16. Item/door/location/movement mechanics ===")
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

print("\n=== 17. Relationship rules + hierarchy in system prompt ===")
results.append(check("NPC RELATIONSHIP RULES present", "NPC RELATIONSHIP RULES:" in SYSTEM_PROMPT))
results.append(check(
    "Relationships in SUBJECTIVE hierarchy",
    "- NPC relationships" in SYSTEM_PROMPT,
))
results.append(check(
    "Relationship never mutates game state",
    "A relationship must never directly mutate game state" in SYSTEM_PROMPT,
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
