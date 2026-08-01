import builtins
import os
import tempfile
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
result = interact(game, "old man", "the forest")
results.append(check("Interact succeeds", result.success))
results.append(check("Memory recorded", len(old_man.memory) >= 1))

print("\n=== 2. Beliefs appear in context, distinct from Knowledge ===")
context = build_game_context(game)
results.append(check("Beliefs section present", "Beliefs:" in context))
results.append(check("Knowledge section present", "Knowledge:" in context))
results.append(check(
    "Beliefs come after Knowledge",
    context.index("Knowledge:") < context.index("Beliefs:"),
))
results.append(check(
    "Belief content present",
    "Nobody has entered the upstairs room recently." in context,
))

print("\n=== 3/4. Belief question prompt carries grounding + belief ===")
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
        return (
            '{"actions": [{"type": "interact", "target": "old_man", '
            '"topic": "Has anyone entered the upstairs room?"}]}'
        )

    def close(self):
        pass


engine = GameEngine()
engine.ai = MockAI()
old_input = builtins.input
builtins.input = lambda _="": ""
try:
    result = engine.process_input(
        "Ask the Old Man if anyone has entered the upstairs room."
    )
finally:
    builtins.input = old_input

results.append(check(
    "Belief presented with Beliefs label in context",
    "Beliefs:" in captured["prompt"],
))
results.append(check(
    "Belief content available to AI",
    "Nobody has entered the upstairs room recently." in captured["prompt"],
))
results.append(check(
    "AI told beliefs are subjective opinions",
    "opinions, assumptions, suspicions" in captured["system"],
))
results.append(check(
    "AI told not to present belief as objective fact",
    "Do NOT present a belief as objective fact" in captured["system"],
))
results.append(check(
    "AI told beliefs may be incorrect",
    "They may be incorrect." in captured["system"],
))
results.append(check(
    "Interact executes",
    result.get("success") is True,
))

print("\n=== 5. Knowledge vs Beliefs vs Memory vs Personality distinct ===")
results.append(check("Personality intact", "Personality:" in context))
results.append(check("Memory intact", "Memory:" in context))
results.append(check(
    "Order: Personality < Memory < Knowledge < Beliefs",
    context.index("Personality:") < context.index("Memory:")
    and context.index("Memory:") < context.index("Knowledge:")
    and context.index("Knowledge:") < context.index("Beliefs:"),
))

print("\n=== 6. Save/load persists beliefs ===")
path = Path(tempfile.gettempdir()) / "test_beliefs_save.json"
save_game(game, path=path)
loaded = load_game(path=path)
lom = loaded.world.npcs["old_man"]
results.append(check("Beliefs persisted", lom.beliefs == old_man.beliefs))
results.append(check("Knowledge persisted", lom.knowledge == old_man.knowledge))
results.append(check("Memory persisted", lom.memory == old_man.memory))
results.append(check("Personality persisted", lom.personality == old_man.personality))
results.append(check(
    "Beliefs present in rebuilt context after load",
    "Nobody has entered the upstairs room recently."
    in build_game_context(loaded),
))
os.remove(path)

print("\n=== 7. Item/door/location/movement mechanics ===")
g2 = create_new_game()
g2.player.location = "upstairs"
door = g2.world.interactables["locked_upstairs_door"]

r = use_item(g2, "Rusty Key", "door")
results.append(check("Unlock works", r.success and door.state == "unlocked"))

r = use_item(g2, "Torn Note", "door")
results.append(check(
    "Wrong item protected",
    "Torn Note" in g2.player.inventory and door.state == "unlocked",
))

r = open_interactable(g2, "door", engine.ai)
results.append(check("Door opens + generates location", r.success and door.state == "open"))

r = move_player(g2, "upstairs", engine.ai)
results.append(check(
    "Movement into generated location works",
    r.success and g2.current_location().name == "Master Bedroom",
))

print("\n=== 8. Belief rules in system prompt ===")
results.append(check("NPC BELIEF RULES present", "NPC BELIEF RULES:" in SYSTEM_PROMPT))
results.append(check(
    "Authoritative/subjective hierarchy present",
    "CRITICAL: AUTHORITATIVE VS SUBJECTIVE HIERARCHY" in SYSTEM_PROMPT,
))
results.append(check(
    "Belief never overrides reality",
    "must never change the actual game state" in SYSTEM_PROMPT,
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
