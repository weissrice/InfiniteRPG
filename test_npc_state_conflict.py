import builtins
import json

from engine.world import create_new_game
from engine.context import build_game_context
from engine.game import SYSTEM_PROMPT, GameEngine


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 1. Conflict rules section present ===")
results.append(check(
    "NPC STATE CONFLICT RULES section present",
    "NPC STATE CONFLICT RULES:" in system,
))
results.append(check(
    "Current authoritative state wins over subjective state",
    "Current authoritative game state always wins over subjective NPC state" in normalized,
))
results.append(check(
    "Beliefs cannot override current state",
    "NPC Beliefs cannot override current authoritative game state" in normalized,
))
results.append(check(
    "Knowledge cannot override current state",
    "NPC Knowledge cannot override current authoritative game state" in normalized,
))

print("\n=== 2. Contradiction does not auto-delete or rewrite state ===")
results.append(check(
    "No automatic belief deletion/update",
    "A contradiction does NOT automatically delete or update the NPC's"
    in normalized,
))
results.append(check(
    "Stored subjective state remains exactly as supplied",
    "The stored subjective state remains exactly as supplied" in normalized,
))
results.append(check(
    "Do not rewrite current state to match belief",
    "Do NOT rewrite the current state to match the NPC's belief" in normalized,
))

print("\n=== 3. NPC may acknowledge the contradiction naturally ===")
results.append(check(
    "NPC may acknowledge reality differs",
    "The NPC may acknowledge that reality differs" in normalized,
))
results.append(check(
    "Dialogue behavior patterns present",
    "I thought..." in system and "That's strange..." in system,
))
results.append(check(
    "Must not claim contradicted belief is currently true",
    "The NPC must NOT claim the contradicted belief is currently true" in normalized,
))

print("\n=== 4. No invented cause ===")
results.append(check(
    "Do not invent a cause for the contradiction",
    "Do NOT invent a cause for the contradiction" in normalized,
))
results.append(check(
    "Personality cannot create an explanation",
    "Someone must have broken the lock" in system,
))

print("\n=== 5. Subjective state cannot mutate authoritative state ===")
results.append(check(
    "Goal conflicts forbid locking doors",
    "must NOT teleport the player, block movement, lock doors" in normalized,
))
results.append(check(
    "Relationship conflicts forbid attacking/blocking",
    "does not allow attacking or blocking" in normalized,
))
results.append(check(
    "Knowledge must not claim door locked because it has a lock",
    "has a lock\" is a property of the door" in normalized,
))

print("\n=== 6. Controlled state: door OPEN + contradictory belief, both visible ===")
game = create_new_game()
game.player.location = "upstairs"
game.world.locations["upstairs"].npcs.append("old_man")
door = game.world.interactables["locked_upstairs_door"]
door.state = "open"
old_man = game.world.npcs["old_man"]
old_man.beliefs.append("The upstairs door is still locked.")
old_man.memory.append("The player asked about the upstairs door yesterday.")

context = build_game_context(game)
results.append(check(
    "Context shows door CURRENT STATE: open",
    "CURRENT STATE: open" in context,
))
results.append(check(
    "Context shows the contradictory belief",
    "The upstairs door is still locked." in context,
))

print("\n=== 7. Prompt sent to AI carries conflict rules + both facts ===")
captured = []


class MockAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        captured.append((system, prompt))
        return json.dumps({
            "narration": (
                "The Old Man peers at the hallway, startled. "
                "\"That's strange. I was sure that door was still locked.\""
            ),
            "actions": [{
                "type": "interact",
                "target": "old_man",
                "topic": "the upstairs door",
            }],
        })

    def close(self):
        pass


before_beliefs = list(old_man.beliefs)
before_goals = list(old_man.goals)
before_relationships = dict(old_man.relationships)
before_personality = list(old_man.personality)
before_memory = list(old_man.memory)

engine = GameEngine()
engine.game = game
engine.ai = MockAI()
old_input = builtins.input
builtins.input = lambda _="": ""

try:
    engine.process_input(
        "ask old man: the upstairs door is open now. "
        "what do you think about that?"
    )
finally:
    builtins.input = old_input

prompt_system, prompt = captured[0]
results.append(check(
    "System prompt carries conflict rules",
    "NPC STATE CONFLICT RULES:" in prompt_system,
))
results.append(check(
    "Prompt carries door CURRENT STATE: open",
    "CURRENT STATE: open" in prompt,
))
results.append(check(
    "Prompt carries the contradictory belief",
    "The upstairs door is still locked." in prompt,
))

print("\n=== 8. Subjective state intact after processing ===")
results.append(check(
    "Belief not auto-deleted",
    old_man.beliefs == before_beliefs,
))
results.append(check(
    "Memory preserved",
    before_memory == old_man.memory[:len(before_memory)],
))
results.append(check(
    "Goals intact",
    old_man.goals == before_goals,
))
results.append(check(
    "Relationships intact",
    old_man.relationships == before_relationships,
))
results.append(check(
    "Personality intact",
    old_man.personality == before_personality,
))

print("\n=== 9. Authoritative state unchanged after processing ===")
results.append(check(
    "Door still open after processing",
    door.state == "open",
))
results.append(check(
    "Door's used flag unchanged",
    door.used is False,
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
