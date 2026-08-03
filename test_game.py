import builtins
import json

from engine.game import GameEngine


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []


class MockAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        return json.dumps({
            "narration": "You step outside into the forest.",
            "actions": [{
                "type": "move",
                "destination": "outside",
            }],
        })

    def close(self):
        pass


print("=== 1. GameEngine initialization ===")
engine = GameEngine()
results.append(check(
    "GameEngine creates game state",
    engine.game is not None,
))
results.append(check(
    "Starting location is set",
    engine.game.current_location() is not None,
))
engine.close()

print("\n=== 2. process_input with mock AI ===")
engine = GameEngine()
engine.ai = MockAI()
old = builtins.input
builtins.input = lambda _="": ""
try:
    result = engine.process_input("Go outside.")
finally:
    builtins.input = old

results.append(check(
    "process_input returns success",
    result.get("success") is True,
))
results.append(check(
    "Returns narration",
    isinstance(result.get("narration"), str) and len(result["narration"]) > 0,
))
results.append(check(
    "Returns actions list",
    isinstance(result.get("actions"), list),
))
results.append(check(
    "Action succeeded",
    result["actions"][0]["success"] is True,
))
results.append(check(
    "Player moved to forest_edge",
    engine.game.player.location == "forest_edge",
))
engine.close()

print("\n=== 3. Save and load round-trip ===")
engine = GameEngine()
engine.ai = MockAI()
old = builtins.input
builtins.input = lambda _="": ""
try:
    engine.process_input("Go outside.")
finally:
    builtins.input = old

# Save
engine.save()

# Load into new engine
engine2 = GameEngine()
engine2.load()
results.append(check(
    "Loaded location matches saved location",
    engine2.game.player.location == engine.game.player.location,
))
results.append(check(
    "Loaded inventory matches saved inventory",
    engine2.game.player.inventory == engine.game.player.inventory,
))
engine.close()
engine2.close()

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
