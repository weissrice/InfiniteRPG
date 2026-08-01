import builtins
from engine.world import create_new_game
from engine.context import build_game_context
from engine.game import SYSTEM_PROMPT, GameEngine


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


game = create_new_game()

results = []

print("=== SCENARIO 1: Game state context != NPC knowledge ===")

context = build_game_context(game)

results.append(check(
    "Context has global WORLD STATE section",
    "=== WORLD STATE ===" in context,
))
results.append(check(
    "Context has NPC Knowledge section",
    "Knowledge:" in context,
))
results.append(check(
    "Context notes world state is not auto-known by NPCs",
    "Global world-state info above is NOT automatically known by any NPC" in context,
))

system = SYSTEM_PROMPT

results.append(check(
    "System prompt has CRITICAL grounding block",
    "CRITICAL: GAME STATE CONTEXT != NPC KNOWLEDGE" in system,
))
results.append(check(
    "System prompt forbids claiming world state as NPC knowledge",
    "Do NOT treat general world-state information as automatically known" in system,
))
results.append(check(
    "System prompt requires uncertainty when NPC lacks a source",
    "I couldn't tell you. I haven't been out there." in system,
))

print("\n=== SCENARIO 2: No invented forest facts in Old Man's knowledge ===")

old_man = game.world.npcs["old_man"]

results.append(check(
    "Old Man knowledge has no invented forest conditions",
    not any(
        word in fact.lower()
        for fact in old_man.knowledge
        for word in ("quiet", "raining", "dangerous", "calm", "misty")
    ),
))

print("\n=== SCENARIO 3: Prompt for forest question carries the grounding rules ===")

captured = {}


class MockAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        captured["system"] = system
        captured["prompt"] = prompt
        return (
            '{"actions": [{"type": "interact", "target": "old_man", '
            '"topic": "What is happening in the forest right now?"}]}'
        )

    def close(self):
        pass


game_engine = GameEngine()
game_engine.ai = MockAI()
old_input = builtins.input
builtins.input = lambda _="": ""
try:
    result = game_engine.process_input(
        "Ask the Old Man what is happening in the forest right now."
    )
finally:
    builtins.input = old_input

results.append(check(
    "Grounding rules present in system prompt sent to AI",
    "GAME STATE CONTEXT != NPC KNOWLEDGE" in captured["system"],
))
results.append(check(
    "Uncertainty guidance present in system prompt sent to AI",
    "the NPC should express uncertainty" in captured["system"],
))
results.append(check(
    "Old Man knowledge facts still present for AI to use",
    "The northern road leads toward the forest." in captured["prompt"],
))
results.append(check(
    "Forest conditions appear only as Beliefs, not Knowledge",
    "quiet" not in context.split("Knowledge:")[1].split("Beliefs:")[0],
))
results.append(check(
    "Forest condition belief present and labeled subjective",
    "The forest is likely quiet this time of day." in context,
))
results.append(check(
    "Interact action executed",
    result.get("success") is True,
))

print("\n=== SCENARIO 4: Old Man can still answer facts in his knowledge ===")

captured.clear()
game_engine.ai = MockAI()
old_input = builtins.input
builtins.input = lambda _="": ""
try:
    result = game_engine.process_input(
        "Ask the Old Man about the upstairs floor."
    )
finally:
    builtins.input = old_input

results.append(check(
    "Upstairs knowledge fact present in prompt",
    "The house has an upstairs floor." in captured["prompt"],
))
results.append(check(
    "Locked door knowledge fact present in prompt",
    "The upstairs door is old and has a lock." in captured["prompt"],
))
results.append(check(
    "Interact action executed",
    result.get("success") is True,
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
