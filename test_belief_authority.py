import builtins
import json

from engine.game import SYSTEM_PROMPT, GameEngine
from engine.context import build_game_context
from engine.world import create_new_game


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 1. Supplied beliefs are authoritative for the NPC's opinion ===")
results.append(check(
    "Authoritative opinion block present",
    "A SUPPLIED BELIEF IS AUTHORITATIVE FOR THE NPC'S CURRENT OPINION"
    in system,
))
results.append(check(
    "Answer in line with supplied belief, do not contradict",
    "Do NOT contradict it." in system,
))
results.append(check(
    "Natural phrasing with uncertainty allowed",
    "may add uncertainty or hedging" in normalized,
))
results.append(check(
    "Cannot soften belief into opposite",
    "Do not soften a supplied belief into its opposite" in normalized,
))
results.append(check(
    "Belief only changes via implemented mechanic",
    "may only change if an implemented mechanic" in normalized,
))
results.append(check(
    "Belief still held while listed in game state",
    "the NPC still holds it" in normalized,
))
results.append(check(
    "Belief takes precedence over knowledge-uncertainty guidance",
    "takes precedence over the knowledge-uncertainty" in normalized,
))
results.append(check(
    "Cannot fall back to 'haven't been out there' when belief applies",
    'do NOT fall back to "I couldn\'t tell you' in normalized,
))
results.append(check(
    "Hedged belief is still the NPC's held opinion",
    "still the NPC's held opinion" in normalized,
))

print("\n=== 2. Context lists the quiet-forest belief ===")
game = create_new_game()
context = build_game_context(game)
results.append(check(
    "Quiet-forest belief present in context",
    "The forest is likely quiet this time of day." in context,
))
results.append(check(
    "Context note reinforces belief authority",
    "should be expressed, not contradicted" in context,
))

print("\n=== 3. Exact repro prompt: 'do you think the forest is quiet right now?' ===")

captured = {}


class MockAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        captured["system"] = system
        captured["prompt"] = prompt
        return json.dumps({
            "narration": (
                "The Old Man nods. \"I think it's probably quiet at "
                "this hour, yes.\""
            ),
            "actions": [{
                "type": "interact",
                "target": "old_man",
                "topic": "do you think the forest is quiet right now?",
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
        "do you think the forest is quiet right now?"
    )
finally:
    builtins.input = old_input

results.append(check(
    "Belief authority rule present in system prompt sent to AI",
    "A SUPPLIED BELIEF IS AUTHORITATIVE" in captured["system"],
))
results.append(check(
    "Precedence rule present in system prompt sent to AI",
    "takes precedence over the knowledge-uncertainty"
    in " ".join(captured["system"].split()),
))
results.append(check(
    "Quiet-forest belief available to AI",
    "The forest is likely quiet this time of day." in captured["prompt"],
))
results.append(check(
    "Exact player question present in prompt",
    "do you think the forest is quiet right now?"
    in captured["prompt"],
))
results.append(check(
    "Belief is associated with Old Man in context",
    captured["prompt"].index("Beliefs:") > captured["prompt"].index("Old Man"),
))
results.append(check(
    "Interact executes",
    result.get("success") is True,
))

print("\n=== 4. Mock reply agrees with the supplied belief ===")
narration = result.get("narration", "")
results.append(check(
    "Narration answers in line with the belief",
    "quiet" in narration.lower(),
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
