import json
import os
from pathlib import Path

from engine.world import create_new_game
from engine.context import build_game_context
from engine.game import SYSTEM_PROMPT
from engine.actions import wait
from engine.routines import advance_npc_routines
from engine.state import NPC
from engine.save import save_game, load_game


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 0. Prompt contains NPC ROUTINE RULES ===")
results.append(check(
    "NPC ROUTINE RULES section present",
    "NPC ROUTINE RULES:" in system,
))
results.append(check(
    "Python moves NPCs per schedule",
    "Python moves the NPC to the scheduled location when game time advances" in normalized,
))
results.append(check(
    "AI must not move NPCs",
    "Do NOT move NPCs, teleport them" in normalized,
))
results.append(check(
    "Routine grants no permission",
    "a routine never grants permission to mutate game state" in normalized,
))
results.append(check(
    "No autonomous routine changes in this response",
    "Routine changes do not happen autonomously in this response" in normalized,
))
results.append(check(
    "Routine memory records the NPC's own movement",
    "records the NPC's own recent routine movement" in normalized,
))
results.append(check(
    "Movement memory acknowledged in reply",
    "Acknowledge the recorded movement in the reply" in normalized,
))
results.append(check(
    "Movement memory takes precedence over Routine list",
    "takes precedence over the descriptive \"Routine\" list" in normalized,
))
results.append(check(
    "Precedence Good example present",
    '"Ah, I went to the kitchen earlier."' in normalized,
))
results.append(check(
    "Copyable denial phrase removed from prompt",
    '"I\'ve been here all along, just tending the fire."' not in normalized
    and 'Do not answer "I haven\'t gone anywhere"' not in normalized,
))
results.append(check(
    "Never deny a recorded movement memory",
    "Never deny a recorded movement memory" in normalized
    and "speaks about it in first person" in normalized,
))
results.append(check(
    "Responses grounded in recorded memory, no invented activity",
    "grounded in the recorded memory" in normalized
    and "Do not invent additional activity or events" in normalized,
))

print("\n=== 0b. Repro prompt carries routine memory + ownership rule ===")
import builtins
from engine.game import GameEngine

captured = {}


class MockAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        captured["system"] = system
        captured["prompt"] = prompt
        return json.dumps({
            "narration": (
                "The Old Man nods. \"Aye, I went to the kitchen "
                "to prepare the evening meal.\""
            ),
            "actions": [{
                "type": "interact",
                "target": "old_man",
                "topic": "did you go somewhere recently",
            }],
        })

    def close(self):
        pass


engine = GameEngine()
engine.game = create_new_game()
engine.game.player.location = "kitchen"
engine.game.world.locations["kitchen"].npcs = []
wait(engine.game, 360)
engine.ai = MockAI()
old_input = builtins.input
builtins.input = lambda _="": ""
try:
    engine.process_input("ask old man: did you go somewhere recently?")
finally:
    builtins.input = old_input

results.append(check(
    "Routine memory entry present in prompt",
    "Old Man went to Kitchen." in captured["prompt"],
))
results.append(check(
    "Movement precedence rule carried in system prompt",
    "takes precedence over the descriptive \"Routine\" list"
    in " ".join(captured["system"].split()),
))
results.append(check(
    "Good example carried in system prompt for repro",
    '"Ah, I went to the kitchen earlier."'
    in " ".join(captured["system"].split()),
))
results.append(check(
    "Direction rule carried in system prompt for player question",
    "The NPC named inside the player's command is NOT the actor"
    in " ".join(captured["system"].split()),
))

print("\n=== 1. Seed data present ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
results.append(check(
    "Old Man has routine",
    "Tends the fire" in old_man.routine,
))
results.append(check(
    "Old Man has schedule",
    old_man.schedule.get("18") == "kitchen",
))

print("\n=== 2. Schedule-driven movement on wait ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
house = game.world.locations["old_wooden_house"]
kitchen = game.world.locations["kitchen"]
results.append(check(
    "Old Man starts at the house",
    old_man.location == "old_wooden_house"
    and "old_man" in house.npcs,
))
res = wait(game, 360)
results.append(check(
    "Time advances to 18:00",
    game.world.time == "18:00",
))
results.append(check(
    "Wait result reports routine change",
    "routine_changes" in res.data
    and "Old Man moved to Kitchen." in res.data["routine_changes"],
))
results.append(check(
    "Old Man moved to kitchen",
    old_man.location == "kitchen"
    and "old_man" in kitchen.npcs,
))
results.append(check(
    "Old Man removed from house",
    "old_man" not in house.npcs,
))
results.append(check(
    "Movement memory recorded",
    "Old Man went to Kitchen." in old_man.memory,
))

print("\n=== 3. Moving back per schedule ===")
res = wait(game, 180)
results.append(check(
    "Time advances to 21:00",
    game.world.time == "21:00",
))
results.append(check(
    "Old Man returns to the house",
    old_man.location == "old_wooden_house"
    and "old_man" in house.npcs
    and "old_man" not in kitchen.npcs,
))
results.append(check(
    "Return movement memory recorded",
    "Old Man went to Old Wooden House." in old_man.memory,
))

print("\n=== 4. No-schedule NPC stays put ===")
game = create_new_game()
game.world.npcs["wanderer"] = NPC(
    id="wanderer",
    name="Wanderer",
    location="forest_edge",
    description="A quiet wanderer.",
)
game.world.locations["forest_edge"].npcs.append("wanderer")
changes = advance_npc_routines(game)
results.append(check(
    "No-schedule NPC not moved",
    game.world.npcs["wanderer"].location == "forest_edge"
    and "wanderer" in game.world.locations["forest_edge"].npcs,
))
results.append(check(
    "No changes reported for it",
    not any("Wanderer" in c for c in changes),
))

print("\n=== 5. Nonexistent schedule target skipped ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
old_man.schedule["13"] = "nonexistent_room"
house = game.world.locations["old_wooden_house"]
before = (old_man.location, list(house.npcs), list(old_man.memory))
res = wait(game, 60)
after = (old_man.location, list(house.npcs), list(old_man.memory))
results.append(check(
    "Nonexistent target ignored, state unchanged",
    before == after and game.world.time == "13:00",
))
results.append(check(
    "No routine change reported",
    "routine_changes" not in res.data,
))

print("\n=== 6. Routine + schedule rendered in context ===")
game = create_new_game()
ctx = build_game_context(game)
results.append(check(
    "Routine section in context",
    "Routine:" in ctx and "Tends the fire" in ctx,
))
results.append(check(
    "Routine marked as descriptive, not an event record",
    "Routine: (descriptive habits" in ctx
    and "NOT a record of specific events or movements" in ctx,
))
results.append(check(
    "Schedule section in context",
    "Schedule:" in ctx and "18:00 → Kitchen" in ctx,
))
results.append(check(
    "Schedule marked as Python-driven location",
    "Schedule: (hour" in ctx
    and "where Python moves the NPC" in ctx,
))
game.world.npcs["old_man"].memory.append("Old Man went to Kitchen.")
ctx_with_memory = build_game_context(game)
results.append(check(
    "Memory marked as authoritative recorded events",
    "Memory: (recorded events - authoritative)" in ctx_with_memory,
))

print("\n=== 7. Save/load round-trip preserves routine + schedule ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
path = Path("test_routine_save.json")
try:
    save_game(game, path)
    loaded = load_game(path)
    loaded_old_man = loaded.world.npcs["old_man"]
    results.append(check(
        "Routine preserved on load",
        loaded_old_man.routine == old_man.routine,
    ))
    results.append(check(
        "Schedule preserved on load",
        loaded_old_man.schedule == old_man.schedule,
    ))
finally:
    if path.exists():
        os.remove(path)

print("\n=== 8. Player wait behavior unchanged ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
old_man.schedule = {}
res = wait(game, 30)
results.append(check(
    "Wait without schedule changes works",
    res.success is True and res.message == "You wait for 30 minutes.",
))
results.append(check(
    "Time advanced normally",
    game.world.time == "12:30",
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
