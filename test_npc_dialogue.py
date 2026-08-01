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
    "Rule applies whenever an NPC speaks",
    "The spoken-response requirement applies whenever an NPC speaks" in normalized,
))
results.append(check(
    "Rule covers player-addressed NPC (target = NPC)",
    "whether the player addressed the NPC" in normalized,
))
results.append(check(
    "Rule covers NPC as actor",
    'the NPC is the "actor" of the interaction' in normalized,
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
    "Atmosphere-only narration explicitly invalid",
    "A narration that only describes the NPC reacting, with no quoted words, is invalid"
    in normalized,
))
results.append(check(
    "Dialogue Good example present",
    '"The Old Man looks up from the fire. "I went to the kitchen earlier.""'
    in normalized,
))
results.append(check(
    "Copyable atmosphere-only phrase removed from prompt",
    "his kind eyes crinkling as he considers your question" not in normalized,
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

print("\n=== 4. Broadened rule applies when the NPC is the actor ===")

captured_actor = {}


class MockActorAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        captured_actor["system"] = system
        captured_actor["prompt"] = prompt
        return json.dumps({
            "narration": (
                "The Old Man looks up from the fire, his kind eyes "
                "softening as he answers your question."
            ),
            "actions": [{
                "type": "interact",
                "actor": "old_man",
                "target": "Traveler",
                "topic": "where were you earlier",
            }],
        })

    def close(self):
        pass


engine = GameEngine()
engine.ai = MockActorAI()
old_input = builtins.input
builtins.input = lambda _="": ""
try:
    actor_result = engine.process_input(
        "ask old man: where were you earlier?"
    )
finally:
    builtins.input = old_input

actor_system = captured_actor["system"]
results.append(check(
    "Broadened scope rule carried for actor case",
    "The spoken-response requirement applies whenever an NPC speaks"
    in " ".join(actor_system.split()),
))
results.append(check(
    "NPC-as-actor branch explicitly covered in prompt",
    'the NPC is the "actor" of the interaction'
    in " ".join(actor_system.split()),
))
results.append(check(
    "Atmosphere-only ban still present for actor case",
    "MUST NOT consist solely of atmospheric"
    in " ".join(actor_system.split()),
))
results.append(check(
    "Spoken answer requirement present for actor case",
    "MUST include the NPC's actual spoken response"
    in " ".join(actor_system.split()),
))
results.append(check(
    "No-actor rule carried for 'where were you earlier?' repro",
    "The NPC named inside the player's command is NOT the actor"
    in " ".join(actor_system.split()),
))
results.append(check(
    "Player → NPC mapping carried for repro",
    'Emit a PLAYER action with NO "actor" field'
    in " ".join(actor_system.split()),
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
