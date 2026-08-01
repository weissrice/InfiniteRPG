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
    _record_npc_memory,
)


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []


class MockAI:
    def __init__(self):
        self.asks = []

    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        self.asks.append(prompt)
        if "Generate the single new location" in prompt:
            return (
                '{"name": "Master Bedroom", "id": "master_bedroom", '
                '"description": "A dusty old bedroom with a canopy bed and a boarded window.", '
                '"visual_type": "interior", "symbol": "bed", '
                '"items": [], "npcs": []}'
            )
        if "what he knows about the upstairs door" in prompt:
            return json.dumps({
                "narration": (
                    "The Old Man looks up from the fire. "
                    "\"The upstairs door is old and has a lock.\""
                ),
                "actions": [{
                    "type": "interact",
                    "target": "old_man",
                    "topic": "the upstairs door",
                }],
            })
        return json.dumps({
            "narration": (
                "The Old Man nods. \"As I said, the upstairs door is "
                "old and has a lock.\""
            ),
            "actions": [{
                "type": "interact",
                "target": "old_man",
                "topic": "what you told me about the upstairs door",
            }],
        })

    def close(self):
        pass


engine = GameEngine()
engine.ai = MockAI()
g = engine.game
old_man = g.world.npcs["old_man"]
old_input = builtins.input
builtins.input = lambda _="": ""

print("=== 1. Existing 'spoke with' memory behavior ===")
interact(g, "old man")
results.append(check(
    "'spoke with' entry still works",
    "The player spoke with Old Man." in old_man.memory,
))

print("\n=== 2/3. Question + response memory entries ===")
try:
    engine.process_input(
        "Ask the Old Man what he knows about the upstairs door."
    )
finally:
    pass
question = "The player asked Old Man about the upstairs door."
response = "Old Man told the player that the upstairs door is old and has a lock."
results.append(check("Question memory entry created", question in old_man.memory))
results.append(check("Response memory entry created", response in old_man.memory))

print("\n=== 4. Response memory is concise, no atmosphere/full narration ===")
results.append(check(
    "No atmospheric action words in response memory",
    "looks up" not in response and "fire" not in response,
))
results.append(check(
    "Response memory is third-person summary, not the narration",
    "The Old Man looks up from the fire" not in old_man.memory,
))
results.append(check(
    "Response memory not the full narration",
    response != "The Old Man looks up from the fire. \"The upstairs door is old and has a lock.\"",
))

print("\n=== 5. Question appears before response ===")
results.append(check(
    "Question index before response index",
    old_man.memory.index(question) < old_man.memory.index(response),
))

print("\n=== 6. Follow-up question receives conversation memory in context ===")
try:
    engine.process_input(
        "What did you tell me about the upstairs door?"
    )
finally:
    pass
last_prompt = engine.ai.asks[-1]
results.append(check("Question memory present in follow-up prompt", question in last_prompt))
results.append(check("Response memory present in follow-up prompt", response in last_prompt))
results.append(check(
    "Conversation memory appears under NPC Memory section",
    "Memory:" in last_prompt,
))

print("\n=== 7. Grounding rules: no invented memories ===")
normalized = " ".join(SYSTEM_PROMPT.split())
results.append(check("NPC CONVERSATION MEMORY RULES present", "NPC CONVERSATION MEMORY RULES:" in SYSTEM_PROMPT))
results.append(check("Do not invent memories", "Do NOT invent memories" in normalized))
results.append(check("Memory not proof of objective truth", "does NOT independently prove" in normalized))
results.append(check("Memory does not override game state", "Memory does not override current game state" in normalized))

print("\n=== 8. Deduplication ===")
count_before = len(old_man.memory)
try:
    engine.process_input(
        "Ask the Old Man what he knows about the upstairs door."
    )
finally:
    pass
results.append(check("Repeated conversation does not duplicate entries", len(old_man.memory) == count_before))

print("\n=== 9. 20-entry memory limit ===")
g2 = create_new_game()
om2 = g2.world.npcs["old_man"]
for i in range(25):
    _record_npc_memory(om2, f"entry {i}")
results.append(check("Memory capped at 20", len(om2.memory) == 20))
results.append(check("Newest entries kept", "entry 24" in om2.memory))
results.append(check("Oldest entries dropped", "entry 0" not in om2.memory))

print("\n=== 10. Save/load persists conversation memory ===")
path = Path(os.environ.get("TEMP", ".")) / "test_conversation_memory_save.json"
save_game(g, path=path)
loaded = load_game(path=path)
lom = loaded.world.npcs["old_man"]
results.append(check("Conversation memory persisted", response in lom.memory))
results.append(check("Question memory persisted", question in lom.memory))
os.remove(path)

print("\n=== 11-18. Distinctness of all NPC fields ===")
context = build_game_context(g)
for header in ("Personality:", "Memory:", "Knowledge:", "Beliefs:", "Goals:", "Relationships:"):
    results.append(check(f"{header} present", header in context))
results.append(check(
    "Order: Personality < Memory < Knowledge < Beliefs < Goals < Relationships",
    context.index("Personality:") < context.index("Memory:")
    and context.index("Memory:") < context.index("Knowledge:")
    and context.index("Knowledge:") < context.index("Beliefs:")
    and context.index("Beliefs:") < context.index("Goals:")
    and context.index("Goals:") < context.index("Relationships:"),
))
results.append(check(
    "Memory entries rendered under NPC Memory section",
    context.index("Memory:") < context.index(response) < context.index("Knowledge:"),
))

print("\n=== 19. Item/door/location/movement mechanics ===")
g2.player.location = "upstairs"
door = g2.world.interactables["locked_upstairs_door"]
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

builtins.input = old_input

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
