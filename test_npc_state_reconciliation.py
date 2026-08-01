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

print("=== 1. Knowledge prevents an inappropriate 'I know nothing' response ===")
results.append(check(
    "Knowledge rule: no false ignorance when knowledge exists",
    "must NOT claim to know nothing about that subject" in normalized,
))
results.append(check(
    "Still forbids inventing facts beyond knowledge",
    "Do not invent facts beyond it" in normalized,
))

print("\n=== 2. Goal influences a directly related question ===")
results.append(check(
    "Goal rule: goals influence directly related questions",
    "should influence the NPC's dialogue when the player's question is directly related" in normalized,
))
results.append(check(
    "Goal rule: do not deny/ignore a supplied goal when asked",
    "Do not deny or ignore a supplied goal when directly asked" in normalized,
))
results.append(check(
    "Goal rule: no invented justifications (monsters/treasure etc.)",
    "secret rooms, treasure, dangerous creatures" in normalized,
))

print("\n=== 3. Beliefs remain expressed, not replaced by generic uncertainty ===")
results.append(check(
    "Belief authority block still present",
    "A SUPPLIED BELIEF IS AUTHORITATIVE FOR THE NPC'S CURRENT OPINION" in system,
))
results.append(check(
    "Belief not softened into denial",
    "Do not soften a supplied belief into its opposite" in normalized,
))
results.append(check(
    "Reconciliation forbids false ignorance when state covers topic",
    "Do NOT claim ignorance when the NPC has relevant supplied information" in normalized,
))

print("\n=== 4. Relationship influences direct attitude questions ===")
results.append(check(
    "Relationship rule: reflect score when asked how NPC feels",
    "When the player asks how the NPC feels about them" in normalized,
))
results.append(check(
    "Relationship still not objective truth about the player",
    "NOT objective facts about the other character" in system,
))

print("\n=== 5/6. Memory and Personality distinct + available ===")
game = create_new_game()
game.world.npcs["old_man"].memory.append(
    "The player asked Old Man about the upstairs door."
)
context = build_game_context(game)
results.append(check("Memory section present", "Memory:" in context))
results.append(check("Personality section present", "Personality:" in context))

print("\n=== 7. Complete context order ===")
results.append(check(
    "Order: Personality < Memory < Knowledge < Beliefs < Goals < Relationships",
    context.index("Personality:") < context.index("Memory:")
    and context.index("Memory:") < context.index("Knowledge:")
    and context.index("Knowledge:") < context.index("Beliefs:")
    and context.index("Beliefs:") < context.index("Goals:")
    and context.index("Goals:") < context.index("Relationships:"),
))

print("\n=== 8. Subjective state does not mutate game state ===")
results.append(check(
    "Hierarchy: subjective never mutates game state",
    "it never mutates game state" in normalized,
))
results.append(check(
    "Goal cannot unlock/lock a door",
    "A goal cannot unlock or lock a door" in normalized,
))
results.append(check(
    "Belief cannot change the weather",
    "A belief cannot change the weather" in normalized,
))
results.append(check(
    "Relationship cannot grant ownership",
    "A relationship cannot grant ownership or permission" in normalized,
))
results.append(check(
    "Personality cannot create facts",
    "Personality cannot create facts" in normalized,
))

print("\n=== 9. AI not instructed to invent facts to justify state ===")
results.append(check(
    "No invented explanations for goals/beliefs/attitudes",
    "Do NOT invent additional facts to explain why the NPC has" in normalized,
))

print("\n=== 10a. Reconciliation rules block present ===")
results.append(check(
    "NPC STATE RECONCILIATION RULES section present",
    "NPC STATE RECONCILIATION RULES:" in system,
))
results.append(check(
    "Identify relevant supplied state",
    "Identify which supplied NPC information is relevant" in normalized,
))
results.append(check(
    "Answer the actual question, not deflect",
    "Answer the actual question the player asked" in normalized,
))
results.append(check(
    "No dumping internal fields into dialogue",
    "Never dump internal fields into the reply" in normalized,
))
results.append(check(
    "Recorded Memory is event evidence, not proof of truth",
    "Recorded Memory as evidence that an event/conversation occurred" in normalized,
))

print("\n=== 10b. Repro prompts carry the relevant state + reconciliation rules ===")
captured = []


class MockAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        captured.append((system, prompt))
        return json.dumps({
            "narration": "The Old Man nods. \"That door is old, and it has a lock.\"",
            "actions": [{
                "type": "interact",
                "target": "old_man",
                "topic": "the upstairs door",
            }],
        })

    def close(self):
        pass


engine = GameEngine()
engine.ai = MockAI()
old_input = builtins.input
builtins.input = lambda _="": ""

scenarios = [
    "ask old man: what do you know about the upstairs door?",
    "why don't you want me going upstairs?",
    "what do you believe about the forest?",
    "what do you think of me?",
]

for player_input in scenarios:
    captured.clear()
    try:
        engine.process_input(player_input)
    finally:
        pass
    prompt_system, prompt = captured[0]
    results.append(check(
        f"Prompt for {player_input!r} carries reconciliation rules",
        "NPC STATE RECONCILIATION RULES:" in prompt_system,
    ))

builtins.input = old_input

results.append(check(
    "Knowledge fact present in door prompt",
    "The upstairs door is old and has a lock." in captured[0][1]
    if captured else False,
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
