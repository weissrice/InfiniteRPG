import builtins
import json
import os
from pathlib import Path

from engine.world import create_new_game
from engine.context import build_game_context
from engine.game import SYSTEM_PROMPT, GameEngine
from engine.actions import wait
from engine.routines import update_npc_activities
from engine.state import NPC
from engine.save import save_game, load_game


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 0. Prompt contains NPC ACTIVITY RULES ===")
results.append(check(
    "NPC ACTIVITY RULES section present",
    "NPC ACTIVITY RULES:" in system,
))
results.append(check(
    "Current Activity is authoritative current state",
    "The \"Current Activity\" under an NPC is authoritative game state"
    in normalized,
))
results.append(check(
    "Answer from Current Activity in first person",
    "answer from the Current Activity in first person" in normalized,
))
results.append(check(
    "Activity takes precedence over Routine for the present",
    "takes precedence over the descriptive Routine list" in normalized
    and "the present moment" in normalized,
))
results.append(check(
    "Do not invent a current activity",
    "Do not invent a current activity" in normalized,
))
results.append(check(
    "Activities change only via Python time advance",
    "Activities change only through Python's time-advance mechanic"
    in normalized
    and "Never claim an NPC began or finished an activity" in normalized,
))
results.append(check(
    "Activity grants no permission to mutate state",
    "An activity never grants permission to mutate game state"
    in normalized,
))
results.append(check(
    "No copyable denial/invented-activity phrasing in prompt",
    "I haven't done anything" not in normalized
    and "I'm not doing anything" not in normalized,
))

print("\n=== 0b. Repro: activity carried in the real prompt after a wait ===")
captured = {}


class MockAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        captured["system"] = system
        captured["prompt"] = prompt
        return json.dumps({
            "narration": (
                "The Old Man stirs the pot. \"Preparing the evening "
                "meal, as you can see.\""
            ),
            "actions": [{
                "type": "interact",
                "target": "old_man",
                "topic": "what are you doing?",
            }],
        })

    def close(self):
        pass


engine = GameEngine()
engine.game = create_new_game()
wait(engine.game, 360)
engine.game.player.location = "kitchen"
engine.ai = MockAI()
old_input = builtins.input
builtins.input = lambda _="": ""
try:
    engine.process_input("ask old man: what are you doing?")
finally:
    builtins.input = old_input

results.append(check(
    "Current Activity present in repro prompt",
    "Current Activity: preparing the evening meal" in captured["prompt"],
))
results.append(check(
    "Activity marked authoritative in repro prompt",
    "(authoritative current state)" in captured["prompt"],
))
results.append(check(
    "NPC ACTIVITY RULES carried in system prompt for repro",
    "NPC ACTIVITY RULES:" in captured["system"]
    and "answer from the Current Activity in first person"
    in " ".join(captured["system"].split()),
))

print("\n=== 1. Seed data present ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
results.append(check(
    "Old Man has activity_by_time for schedule hours",
    old_man.activity_by_time.get("12") == "tending the fire"
    and old_man.activity_by_time.get("18") == "preparing the evening meal"
    and old_man.activity_by_time.get("21") == "keeping watch over the house",
))
results.append(check(
    "Old Man starts with the 12:00 activity",
    old_man.current_activity == "tending the fire",
))
results.append(check(
    "Existing routine + schedule semantics unchanged",
    old_man.routine == [
        "Tends the fire",
        "Reads old books by the window",
        "Prepares meals in the kitchen",
        "Keeps watch over the house",
    ]
    and old_man.schedule.get("18") == "kitchen",
))

print("\n=== 2. Wait advances the activity with the schedule move ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
res = wait(game, 360)
results.append(check(
    "Time advances to 18:00",
    game.world.time == "18:00",
))
results.append(check(
    "Activity updates to the 18:00 entry",
    old_man.current_activity == "preparing the evening meal",
))
results.append(check(
    "Wait result reports activity change",
    "activity_changes" in res.data
    and "Old Man is now preparing the evening meal."
    in res.data["activity_changes"],
))
results.append(check(
    "routine_changes still reported separately for the move",
    "routine_changes" in res.data
    and "Old Man moved to Kitchen." in res.data["routine_changes"]
    and "activity_changes" in res.data,
))
results.append(check(
    "Movement still recorded in memory",
    "Old Man went to Kitchen." in old_man.memory,
))

print("\n=== 3. Activity updates again on the return trip ===")
res = wait(game, 180)
results.append(check(
    "Time advances to 21:00",
    game.world.time == "21:00",
))
results.append(check(
    "Activity updates to the 21:00 entry",
    old_man.current_activity == "keeping watch over the house",
))
results.append(check(
    "Old Man returned to the house",
    old_man.location == "old_wooden_house",
))

print("\n=== 4. Activity updates without any movement ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
old_man.schedule["13"] = "old_wooden_house"
old_man.activity_by_time["13"] = "reading old books"
house = game.world.locations["old_wooden_house"]
before = (old_man.location, list(house.npcs))
res = wait(game, 60)
after = (old_man.location, list(house.npcs))
results.append(check(
    "NPC did not move at 13:00",
    before == after and game.world.time == "13:00",
))
results.append(check(
    "Activity changed while staying in place",
    old_man.current_activity == "reading old books",
))
results.append(check(
    "No routine change reported for a stationary hour",
    "routine_changes" not in res.data,
))
results.append(check(
    "Activity change reported independently",
    "activity_changes" in res.data
    and "Old Man is now reading old books." in res.data["activity_changes"],
))

print("\n=== 5. No-activity NPC is untouched ===")
game = create_new_game()
game.world.npcs["wanderer"] = NPC(
    id="wanderer",
    name="Wanderer",
    location="forest_edge",
    description="A quiet wanderer.",
)
game.world.locations["forest_edge"].npcs.append("wanderer")
changes = update_npc_activities(game)
results.append(check(
    "No-activity NPC keeps an empty current activity",
    game.world.npcs["wanderer"].current_activity == "",
))
results.append(check(
    "No activity change reported for it",
    not any("Wanderer" in c for c in changes),
))
game.player.location = "forest_edge"
ctx = build_game_context(game)
results.append(check(
    "No-activity NPC rendered without a Current Activity line",
    "Wanderer" in ctx and "Current Activity:" not in ctx,
))

print("\n=== 6. Current Activity rendered in context ===")
game = create_new_game()
ctx = build_game_context(game)
results.append(check(
    "Current Activity line present with phrase",
    "Current Activity: tending the fire" in ctx,
))
results.append(check(
    "Current Activity marked authoritative",
    "Current Activity: tending the fire "
    "(authoritative current state)" in ctx,
))
results.append(check(
    "Existing Routine + Schedule sections still present",
    "Routine: (descriptive habits" in ctx
    and "Schedule: (hour" in ctx
    and "18:00 → Kitchen" in ctx,
))

print("\n=== 7. Save/load round-trip preserves activity fields ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
wait(game, 360)
path = Path("test_activity_save.json")
try:
    save_game(game, path)
    loaded = load_game(path)
    loaded_old_man = loaded.world.npcs["old_man"]
    results.append(check(
        "current_activity preserved on load",
        loaded_old_man.current_activity == old_man.current_activity
        == "preparing the evening meal",
    ))
    results.append(check(
        "activity_by_time preserved on load",
        loaded_old_man.activity_by_time == old_man.activity_by_time,
    ))
finally:
    if path.exists():
        os.remove(path)

print("\n=== 8. Existing wait behavior unchanged ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
old_man.schedule = {}
old_man.activity_by_time = {}
res = wait(game, 30)
results.append(check(
    "Wait without activity data still works",
    res.success is True and res.message == "You wait for 30 minutes.",
))
results.append(check(
    "Time advanced normally",
    game.world.time == "12:30",
))
results.append(check(
    "No activity or routine change reported",
    "activity_changes" not in res.data
    and "routine_changes" not in res.data,
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
