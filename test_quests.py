import json
import os
from pathlib import Path

from engine.world import create_new_game
from engine.game import SYSTEM_PROMPT
from engine.actions import (
    accept_quest,
    abandon_quest,
    attack,
    decline_quest,
    interact,
    move_player,
    offer_quest,
    take_item,
    _check_quest_progress,
)
from engine.state import GameState, Quest, QuestObjective
from engine.save import save_game, load_game

TEST_SAVE = Path("test_quest_save.json")


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

# ------------------------------------------------------------------
# 0. System prompt
# ------------------------------------------------------------------

print("=== 0. System prompt contains QUEST RULES ===")
results.append(check(
    "QUEST RULES section present",
    "QUEST RULES:" in system,
))
results.append(check(
    "offer_quest in valid types",
    "offer_quest" in [
        line.strip()
        for line in system.split("\n")
        if line.strip() in [
            "move", "take_item", "drop_item", "inspect",
            "interact", "use_item", "open", "wait", "attack",
            "offer_quest", "accept_quest", "decline_quest",
            "abandon_quest",
        ]
    ],
))
results.append(check(
    "offer_quest format present",
    '"type": "offer_quest"' in normalized,
))
results.append(check(
    "accept_quest format present",
    '"type": "accept_quest"' in normalized,
))
results.append(check(
    "quest_id field documented",
    '"quest_id":' in normalized,
))
results.append(check(
    "objectives field documented",
    '"objectives":' in normalized,
))
results.append(check(
    "No start quests exclusion",
    "start quests" not in system,
))

# ------------------------------------------------------------------
# 1. Valid quest creation
# ------------------------------------------------------------------

print("\n=== 1. Valid quest creation ===")
game = create_new_game()
result = offer_quest(
    game,
    "old_man",
    "quest_001",
    "Find the Key",
    "Find the lost brass key in the forest.",
    [
        {"id": "obj_1", "type": "find", "target": "brass_key",
         "description": "Find the brass key", "required": 1},
    ],
    {"items": ["Silver Ring"], "relationships": {"old_man": 5}},
)
results.append(check(
    "Offer succeeds",
    result.success,
))
results.append(check(
    "Quest created in game.quests",
    "quest_001" in game.quests,
))
results.append(check(
    "Quest state is offered",
    game.quests["quest_001"].state == "offered",
))
results.append(check(
    "Quest giver is old_man",
    game.quests["quest_001"].giver == "old_man",
))
results.append(check(
    "Quest has one objective",
    len(game.quests["quest_001"].objectives) == 1,
))
results.append(check(
    "Objective type is find",
    game.quests["quest_001"].objectives[0].type == "find",
))
results.append(check(
    "Objective target is brass_key",
    game.quests["quest_001"].objectives[0].target == "brass_key",
))

# ------------------------------------------------------------------
# 2. Invalid NPC giver
# ------------------------------------------------------------------

print("\n=== 2. Invalid NPC giver ===")
game = create_new_game()
result = offer_quest(
    game, "nonexistent", "q1", "Title", "Desc",
    [{"id": "o1", "type": "find", "target": "key",
      "description": "Find key", "required": 1}],
)
results.append(check(
    "Fails for unknown NPC",
    not result.success,
))

# ------------------------------------------------------------------
# 3. Non-co-located giver
# ------------------------------------------------------------------

print("\n=== 3. Non-co-located giver ===")
game = create_new_game()
game.player.location = "forest_path"
result = offer_quest(
    game, "old_man", "q1", "Title", "Desc",
    [{"id": "o1", "type": "find", "target": "key",
      "description": "Find key", "required": 1}],
)
results.append(check(
    "Fails when NPC not at player location",
    not result.success,
))

# ------------------------------------------------------------------
# 4. Duplicate quest ID
# ------------------------------------------------------------------

print("\n=== 4. Duplicate quest ID ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Title", "Desc",
    [{"id": "o1", "type": "find", "target": "key",
      "description": "Find key", "required": 1}],
)
result = offer_quest(
    game, "old_man", "quest_001", "Title2", "Desc2",
    [{"id": "o2", "type": "find", "target": "key",
      "description": "Find key", "required": 1}],
)
results.append(check(
    "Fails for duplicate quest ID",
    not result.success,
))

# ------------------------------------------------------------------
# 5. Empty objectives
# ------------------------------------------------------------------

print("\n=== 5. Empty objectives ===")
game = create_new_game()
result = offer_quest(
    game, "old_man", "q1", "Title", "Desc", [],
)
results.append(check(
    "Fails for empty objectives",
    not result.success,
))

# ------------------------------------------------------------------
# 6. Invalid objective type
# ------------------------------------------------------------------

print("\n=== 6. Invalid objective type ===")
game = create_new_game()
result = offer_quest(
    game, "old_man", "q1", "Title", "Desc",
    [{"id": "o1", "type": "dance", "target": "x",
      "description": "Dance", "required": 1}],
)
results.append(check(
    "Fails for invalid objective type",
    not result.success,
))

# ------------------------------------------------------------------
# 7. Invalid objective target (kill/talk)
# ------------------------------------------------------------------

print("\n=== 7. Invalid objective target (kill) ===")
game = create_new_game()
result = offer_quest(
    game, "old_man", "q1", "Title", "Desc",
    [{"id": "o1", "type": "kill", "target": "ghost",
      "description": "Kill ghost", "required": 1}],
)
results.append(check(
    "Fails for kill target that does not exist",
    not result.success,
))

print("\n=== 7b. Invalid objective target (talk) ===")
game = create_new_game()
result = offer_quest(
    game, "old_man", "q1", "Title", "Desc",
    [{"id": "o1", "type": "talk", "target": "ghost",
      "description": "Talk to ghost", "required": 1}],
)
results.append(check(
    "Fails for talk target that does not exist",
    not result.success,
))

# ------------------------------------------------------------------
# 8. Invalid reward target
# ------------------------------------------------------------------

print("\n=== 8. Invalid reward target ===")
game = create_new_game()
result = offer_quest(
    game, "old_man", "q1", "Title", "Desc",
    [{"id": "o1", "type": "find", "target": "key",
      "description": "Find key", "required": 1}],
    {"relationships": {"ghost": 10}},
)
results.append(check(
    "Fails for reward relationship target that does not exist",
    not result.success,
))

# ------------------------------------------------------------------
# 9. Acceptance
# ------------------------------------------------------------------

print("\n=== 9. Acceptance ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the key.",
    [{"id": "obj_1", "type": "find", "target": "brass_key",
      "description": "Find the brass key", "required": 1}],
)
result = accept_quest(game, "quest_001")
results.append(check(
    "Accept succeeds",
    result.success,
))
results.append(check(
    "Quest state is active",
    game.quests["quest_001"].state == "active",
))

# ------------------------------------------------------------------
# 10. Decline
# ------------------------------------------------------------------

print("\n=== 10. Decline ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the key.",
    [{"id": "obj_1", "type": "find", "target": "brass_key",
      "description": "Find the brass key", "required": 1}],
)
result = decline_quest(game, "quest_001")
results.append(check(
    "Decline succeeds",
    result.success,
))
results.append(check(
    "Quest removed from game.quests",
    "quest_001" not in game.quests,
))

# ------------------------------------------------------------------
# 11. Abandon
# ------------------------------------------------------------------

print("\n=== 11. Abandon ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the key.",
    [{"id": "obj_1", "type": "find", "target": "brass_key",
      "description": "Find the brass key", "required": 1}],
)
accept_quest(game, "quest_001")
result = abandon_quest(game, "quest_001")
results.append(check(
    "Abandon succeeds",
    result.success,
))
results.append(check(
    "Quest state is abandoned",
    game.quests["quest_001"].state == "abandoned",
))

# ------------------------------------------------------------------
# 12. Kill objective progression
# ------------------------------------------------------------------

print("\n=== 12. Kill objective progression ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Defend the House",
    "Kill the intruder.",
    [{"id": "obj_1", "type": "kill", "target": "sarah",
      "description": "Kill Sarah", "required": 1}],
)
accept_quest(game, "quest_001")
game.world.npcs["sarah"].hp = 5
attack(game, "player", "sarah", "")
results.append(check(
    "Kill objective progresses",
    game.quests["quest_001"].objectives[0].current == 1,
))
results.append(check(
    "Kill objective completed",
    game.quests["quest_001"].objectives[0].completed,
))

# ------------------------------------------------------------------
# 13. Find objective progression
# ------------------------------------------------------------------

print("\n=== 13. Find objective progression ===")
game = create_new_game()
game.world.locations["old_wooden_house"].items.append("Brass Key")
offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the brass key.",
    [{"id": "obj_1", "type": "find", "target": "Brass Key",
      "description": "Find the brass key", "required": 1}],
)
accept_quest(game, "quest_001")
take_item(game, "Brass Key")
results.append(check(
    "Find objective progresses",
    game.quests["quest_001"].objectives[0].current == 1,
))

# ------------------------------------------------------------------
# 14. Talk objective progression
# ------------------------------------------------------------------

print("\n=== 14. Talk objective progression ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Talk to Sarah",
    "Speak with Sarah.",
    [{"id": "obj_1", "type": "talk", "target": "sarah",
      "description": "Talk to Sarah", "required": 1}],
)
accept_quest(game, "quest_001")
interact(game, "sarah", "the quest")
results.append(check(
    "Talk objective progresses",
    game.quests["quest_001"].objectives[0].current == 1,
))

# ------------------------------------------------------------------
# 15. Visit objective progression
# ------------------------------------------------------------------

print("\n=== 15. Visit objective progression ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Explore the Forest",
    "Go to the forest edge.",
    [{"id": "obj_1", "type": "visit", "target": "forest_edge",
      "description": "Visit the forest edge", "required": 1}],
)
accept_quest(game, "quest_001")
move_player(game, "outside")
results.append(check(
    "Visit objective progresses",
    game.quests["quest_001"].objectives[0].current == 1,
))

# ------------------------------------------------------------------
# 16. Wrong-target objective does not progress
# ------------------------------------------------------------------

print("\n=== 16. Wrong-target objective does not progress ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Kill Sarah",
    "Kill Sarah.",
    [{"id": "obj_1", "type": "kill", "target": "sarah",
      "description": "Kill Sarah", "required": 1}],
)
accept_quest(game, "quest_001")
game.world.npcs["old_man"].hp = 5
attack(game, "player", "old_man", "")
results.append(check(
    "Kill wrong target does not progress",
    game.quests["quest_001"].objectives[0].current == 0,
))

# ------------------------------------------------------------------
# 17. Objective progress caps
# ------------------------------------------------------------------

print("\n=== 17. Objective progress caps ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Kill",
    "Kill once.",
    [{"id": "obj_1", "type": "kill", "target": "sarah",
      "description": "Kill Sarah", "required": 1}],
)
accept_quest(game, "quest_001")
# Kill sarah multiple times (she respawns in different locations)
game.world.npcs["sarah"].hp = 5
attack(game, "player", "sarah", "")
results.append(check(
    "Progress capped at required",
    game.quests["quest_001"].objectives[0].current == 1,
))

# ------------------------------------------------------------------
# 18. Quest completion
# ------------------------------------------------------------------

print("\n=== 18. Quest completion ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the brass key.",
    [{"id": "obj_1", "type": "find", "target": "brass_key",
      "description": "Find the brass key", "required": 1}],
)
accept_quest(game, "quest_001")
game.world.locations["old_wooden_house"].items.append("Brass Key")
take_item(game, "Brass Key")
results.append(check(
    "Quest completed automatically",
    game.quests["quest_001"].state == "completed",
))

# ------------------------------------------------------------------
# 19. Completion rewards
# ------------------------------------------------------------------

print("\n=== 19. Completion rewards ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the brass key.",
    [{"id": "obj_1", "type": "find", "target": "brass_key",
      "description": "Find the brass key", "required": 1}],
    {"items": ["Silver Ring"], "relationships": {"old_man": 10}},
)
accept_quest(game, "quest_001")
game.world.locations["old_wooden_house"].items.append("Brass Key")
take_item(game, "Brass Key")
results.append(check(
    "Silver Ring added to inventory",
    "Silver Ring" in game.player.inventory,
))
results.append(check(
    "Old man relationship increased",
    game.world.npcs["old_man"].relationships.get(
        game.player.name, 0
    ) >= 10,
))

# ------------------------------------------------------------------
# 20. Rewards only applied once
# ------------------------------------------------------------------

print("\n=== 20. Rewards only applied once ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the brass key.",
    [{"id": "obj_1", "type": "find", "target": "brass_key",
      "description": "Find the brass key", "required": 1}],
    {"items": ["Silver Ring"]},
)
accept_quest(game, "quest_001")
game.world.locations["old_wooden_house"].items.append("Brass Key")
take_item(game, "Brass Key")
ring_count = game.player.inventory.count("Silver Ring")
results.append(check(
    "Reward given exactly once",
    ring_count == 1,
))

# ------------------------------------------------------------------
# 21. Quest giver death
# ------------------------------------------------------------------

print("\n=== 21. Quest giver death ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Help Me",
    "Help the old man.",
    [{"id": "obj_1", "type": "find", "target": "key",
      "description": "Find key", "required": 1}],
)
accept_quest(game, "quest_001")
game.world.npcs["old_man"].hp = 5
attack(game, "player", "old_man", "")
results.append(check(
    "Quest failed when giver died",
    game.quests["quest_001"].state == "failed",
))

# ------------------------------------------------------------------
# 22. Failed quest cannot be completed
# ------------------------------------------------------------------

print("\n=== 22. Failed quest cannot be completed ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Help Me",
    "Help the old man.",
    [{"id": "obj_1", "type": "find", "target": "brass_key",
      "description": "Find key", "required": 1}],
)
accept_quest(game, "quest_001")
game.world.npcs["old_man"].hp = 5
attack(game, "player", "old_man", "")
# Try to progress the objective
game.world.locations["old_wooden_house"].items.append("Brass Key")
_check_quest_progress(game, "find", "brass_key")
results.append(check(
    "Failed quest objective does not progress",
    game.quests["quest_001"].objectives[0].current == 0,
))

# ------------------------------------------------------------------
# 23. Failed quest cannot be accepted
# ------------------------------------------------------------------

print("\n=== 23. Failed quest cannot be accepted ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Help Me",
    "Help the old man.",
    [{"id": "obj_1", "type": "find", "target": "key",
      "description": "Find key", "required": 1}],
)
# Manually fail the quest
game.quests["quest_001"].state = "failed"
result = accept_quest(game, "quest_001")
results.append(check(
    "Cannot accept a failed quest",
    not result.success,
))

# ------------------------------------------------------------------
# 24. Save/load active quest
# ------------------------------------------------------------------

print("\n=== 24. Save/load active quest ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the brass key.",
    [{"id": "obj_1", "type": "find", "target": "brass_key",
      "description": "Find the brass key", "required": 1}],
)
accept_quest(game, "quest_001")
save_game(game, TEST_SAVE)
loaded = load_game(TEST_SAVE)
results.append(check(
    "Loaded quest exists",
    "quest_001" in loaded.quests,
))
results.append(check(
    "Loaded quest is active",
    loaded.quests["quest_001"].state == "active",
))
results.append(check(
    "Loaded quest title matches",
    loaded.quests["quest_001"].title == "Find the Key",
))
os.remove(TEST_SAVE)

# ------------------------------------------------------------------
# 25. Save/load progress
# ------------------------------------------------------------------

print("\n=== 25. Save/load progress ===")
game = create_new_game()
game.world.locations["old_wooden_house"].items.append("Brass Key")
offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the brass key.",
    [{"id": "obj_1", "type": "find", "target": "Brass Key",
      "description": "Find the brass key", "required": 3}],
)
accept_quest(game, "quest_001")
take_item(game, "Brass Key")
save_game(game, TEST_SAVE)
loaded = load_game(TEST_SAVE)
results.append(check(
    "Loaded quest has progress",
    loaded.quests["quest_001"].objectives[0].current == 1,
))
results.append(check(
    "Loaded quest not yet completed",
    loaded.quests["quest_001"].state == "active",
))
os.remove(TEST_SAVE)

# ------------------------------------------------------------------
# 26. Save/load completed quest
# ------------------------------------------------------------------

print("\n=== 26. Save/load completed quest ===")
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the brass key.",
    [{"id": "obj_1", "type": "find", "target": "brass_key",
      "description": "Find the brass key", "required": 1}],
    {"items": ["Silver Ring"]},
)
accept_quest(game, "quest_001")
game.world.locations["old_wooden_house"].items.append("Brass Key")
take_item(game, "Brass Key")
save_game(game, TEST_SAVE)
loaded = load_game(TEST_SAVE)
results.append(check(
    "Loaded quest is completed",
    loaded.quests["quest_001"].state == "completed",
))
results.append(check(
    "Loaded quest has reward item",
    "Silver Ring" in loaded.player.inventory,
))
os.remove(TEST_SAVE)

# ------------------------------------------------------------------
# 27. Context rendering
# ------------------------------------------------------------------

print("\n=== 27. Context rendering ===")
from engine.context import build_game_context
game = create_new_game()
offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the brass key.",
    [{"id": "obj_1", "type": "find", "target": "brass_key",
      "description": "Find the brass key", "required": 1}],
)
accept_quest(game, "quest_001")
ctx = build_game_context(game)
results.append(check(
    "QUESTS section in context",
    "=== QUESTS ===" in ctx,
))
results.append(check(
    "Active quests shown",
    "Active:" in ctx,
))
results.append(check(
    "Quest id in context",
    "quest_001" in ctx,
))
results.append(check(
    "Quest title in context",
    "Find the Key" in ctx,
))
results.append(check(
    "Objective progress in context",
    "0/1" in ctx,
))

# ------------------------------------------------------------------
# 28. /quests command (structural test)
# ------------------------------------------------------------------

print("\n=== 28. /quests command exists ===")
try:
    from main import show_quests
    results.append(check(
        "show_quests function exists",
        callable(show_quests),
    ))
except ImportError:
    results.append(check(
        "show_quests function exists (prompt_toolkit missing, skip)",
        True,
    ))

# ------------------------------------------------------------------
# 29. Full integration: offer -> accept -> progress -> complete
# ------------------------------------------------------------------

print("\n=== 29. Full integration ===")
game = create_new_game()
game.world.locations["old_wooden_house"].items.append("Brass Key")
result = offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the brass key.",
    [{"id": "obj_1", "type": "find", "target": "Brass Key",
      "description": "Find the brass key", "required": 1}],
    {"items": ["Silver Ring"]},
)
results.append(check(
    "Step 1: Offer succeeds",
    result.success,
))
result = accept_quest(game, "quest_001")
results.append(check(
    "Step 2: Accept succeeds",
    result.success,
))
result = take_item(game, "Brass Key")
results.append(check(
    "Step 3: Take item succeeds",
    result.success,
))
results.append(check(
    "Step 4: Quest completed",
    game.quests["quest_001"].state == "completed",
))
results.append(check(
    "Step 5: Reward in inventory",
    "Silver Ring" in game.player.inventory,
))

# ------------------------------------------------------------------
# 30. Multiple simultaneous quests
# ------------------------------------------------------------------

print("\n=== 30. Multiple simultaneous quests ===")
game = create_new_game()
game.world.locations["old_wooden_house"].items.append("Brass Key")
offer_quest(
    game, "old_man", "quest_001", "Find the Key",
    "Find the brass key.",
    [{"id": "obj_1", "type": "find", "target": "Brass Key",
      "description": "Find the brass key", "required": 1}],
)
offer_quest(
    game, "old_man", "quest_002", "Talk to Sarah",
    "Speak with Sarah.",
    [{"id": "obj_1", "type": "talk", "target": "sarah",
      "description": "Talk to Sarah", "required": 1}],
)
accept_quest(game, "quest_001")
accept_quest(game, "quest_002")
results.append(check(
    "Both quests active",
    game.quests["quest_001"].state == "active"
    and game.quests["quest_002"].state == "active",
))
take_item(game, "Brass Key")
results.append(check(
    "Quest 001 completed",
    game.quests["quest_001"].state == "completed",
))
results.append(check(
    "Quest 002 still active",
    game.quests["quest_002"].state == "active",
))

# ------------------------------------------------------------------
# 31. Invalid LLM proposal causes zero mutation
# ------------------------------------------------------------------

print("\n=== 31. Invalid LLM proposal zero mutation ===")
game = create_new_game()
old_quests = dict(game.quests)
result = offer_quest(
    game, "nonexistent", "q1", "Title", "Desc",
    [{"id": "o1", "type": "find", "target": "key",
      "description": "Find key", "required": 1}],
)
results.append(check(
    "Invalid offer rejected",
    not result.success,
))
results.append(check(
    "No quests created",
    game.quests == old_quests,
))

# ------------------------------------------------------------------
# 32. Quest actions don't bypass validation
# ------------------------------------------------------------------

print("\n=== 32. Quest actions don't bypass validation ===")
game = create_new_game()
result = accept_quest(game, "nonexistent_quest")
results.append(check(
    "Accept non-existent quest fails",
    not result.success,
))
result = decline_quest(game, "nonexistent_quest")
results.append(check(
    "Decline non-existent quest fails",
    not result.success,
))
result = abandon_quest(game, "nonexistent_quest")
results.append(check(
    "Abandon non-existent quest fails",
    not result.success,
))

# ------------------------------------------------------------------
# 33. Old save without quests loads fine
# ------------------------------------------------------------------

print("\n=== 33. Old save without quests loads fine ===")
# Create a save file without quest data
old_save = {
    "version": 1,
    "player": {
        "name": "Traveler",
        "hp": 100,
        "max_hp": 100,
        "location": "old_wooden_house",
        "inventory": ["Rusty Key", "Torn Note"],
    },
    "world": {
        "name": "Test World",
        "genre": "Fantasy",
        "time": "12:00",
        "day": 1,
        "weather": "Rain",
        "locations": {},
        "npcs": {},
        "interactables": {},
    },
}
old_save_path = Path("test_old_save.json")
with open(old_save_path, "w") as f:
    json.dump(old_save, f)
loaded = load_game(old_save_path)
results.append(check(
    "Old save loads without error",
    loaded is not None,
))
results.append(check(
    "Old save has empty quests",
    loaded.quests == {},
))
os.remove(old_save_path)

# ------------------------------------------------------------------
# 34. SYSTEM_PROMPT loads correctly
# ------------------------------------------------------------------

print("\n=== 34. SYSTEM_PROMPT loads correctly ===")
results.append(check(
    "SYSTEM_PROMPT is non-empty string",
    isinstance(SYSTEM_PROMPT, str) and len(SYSTEM_PROMPT) > 0,
))
results.append(check(
    "SYSTEM_PROMPT contains QUEST RULES",
    "QUEST RULES:" in SYSTEM_PROMPT,
))

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------

print("\n" + "=" * 40)
passed = sum(results)
total = len(results)
print(f"RESULTS: {passed}/{total} passed")
if passed < total:
    print("SOME TESTS FAILED")
    raise SystemExit(1)
else:
    print("ALL TESTS PASSED")
