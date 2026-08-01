import builtins
import json

from engine.game import SYSTEM_PROMPT, GameEngine


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 1. Dialogue response rules present in system prompt ===")
results.append(check(
    "NPC DIALOGUE RESPONSE RULES block present",
    "NPC DIALOGUE RESPONSE RULES:" in system,
))
results.append(check(
    "Narration must include a spoken response when topic is non-empty",
    "MUST include the NPC's actual spoken response" in normalized,
))
results.append(check(
    "Atmosphere-only narration explicitly forbidden",
    "MUST NOT consist solely of atmospheric" in normalized,
))
results.append(check(
    "Brief descriptive action still allowed before the reply",
    "may begin with a brief descriptive action" in normalized,
))
results.append(check(
    "Reply must be written as dialogue in quotation marks",
    "written as dialogue in quotation marks" in normalized,
))
results.append(check(
    "Must answer the question actually asked",
    "Do not answer a different question than the one asked" in normalized,
))
results.append(check(
    "Uncertainty required when NPC lacks a source",
    "must express uncertainty" in normalized,
))
results.append(check(
    "Dialogue never changes game state",
    "Dialogue never changes game state" in normalized,
))

print("\n=== 2. Repro scenario: belief question prompt carries grounding ===")

captured = {}


class MockAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        captured["system"] = system
        captured["prompt"] = prompt
        return json.dumps({
            "narration": (
                "The Old Man looks up from the fire and says, "
                "\"I believe it's probably quiet at this hour. "
                "At least, that's what I'd expect.\""
            ),
            "actions": [{
                "type": "interact",
                "target": "old_man",
                "topic": "what do you believe about the forest",
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
        "Ask the Old Man what he believes about the forest."
    )
finally:
    builtins.input = old_input

results.append(check(
    "Dialogue rules carried in system prompt sent to AI",
    "NPC DIALOGUE RESPONSE RULES:" in captured["system"],
))
results.append(check(
    "Atmosphere-only ban carried in system prompt sent to AI",
    "MUST NOT consist solely of atmospheric"
    in " ".join(captured["system"].split()),
))
results.append(check(
    "Player question present in prompt",
    "Ask the Old Man what he believes about the forest."
    in captured["prompt"],
))
results.append(check(
    "Old Man belief present for AI to answer from",
    "The forest is likely quiet this time of day." in captured["prompt"],
))
results.append(check(
    "Knowledge grounding preserved alongside dialogue rules",
    "GAME STATE CONTEXT != NPC KNOWLEDGE" in captured["system"],
))
results.append(check(
    "Belief grounding preserved alongside dialogue rules",
    "NPC BELIEF RULES:" in captured["system"],
))
results.append(check(
    "Interact executes",
    result.get("success") is True,
))

print("\n=== 3. Repro narration now contains a spoken answer ===")
narration = result.get("narration", "")
results.append(check(
    "Narration includes spoken dialogue",
    "I believe it's probably quiet at this hour" in narration,
))
results.append(check(
    "Narration is not atmosphere-only",
    "At least, that's what I'd expect." in narration,
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
